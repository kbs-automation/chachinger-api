import ipaddress
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.redis import get_redis
from app.core.security import TokenError, decode_admin_token, decode_user_token
from app.models import User
from app.services import rate_limit

bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    detail={"code": "not_authenticated", "message": "Not authenticated"},
    headers={"WWW-Authenticate": "Bearer"},
)


def client_ip(request: Request) -> str | None:
    """Rightmost X-Forwarded-For entry is the address the ALB actually saw."""
    forwarded = request.headers.get("x-forwarded-for")
    candidate = forwarded.split(",")[-1].strip() if forwarded else None
    if not candidate and request.client:
        candidate = request.client.host
    try:
        return str(ipaddress.ip_address(candidate)) if candidate else None
    except ValueError:
        return None


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if creds is None:
        raise _UNAUTHORIZED
    try:
        claims = decode_user_token(creds.credentials, "access")
        user_id = uuid.UUID(claims["sub"])
    except (TokenError, ValueError) as exc:
        raise _UNAUTHORIZED from exc
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise _UNAUTHORIZED
    if user.is_suspended:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={"code": "account_suspended", "message": "This account is suspended"},
        )
    return user


async def get_current_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if creds is None:
        raise _UNAUTHORIZED
    try:
        claims = decode_admin_token(creds.credentials)
        user_id = uuid.UUID(claims["sub"])
    except (TokenError, ValueError) as exc:
        raise _UNAUTHORIZED from exc
    user = await db.get(User, user_id)
    if user is None or not user.is_admin or user.deleted_at is not None or user.is_suspended:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail={"code": "forbidden", "message": "Admin only"}
        )
    return user


def _too_many(window: int) -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        detail={"code": "rate_limited", "message": "Too many requests"},
        headers={"Retry-After": str(window)},
    )


def ip_rate_limit(name: str, limit: int, window: int) -> Callable[..., Awaitable[None]]:
    async def dependency(request: Request, redis: Redis = Depends(get_redis)) -> None:
        if not get_settings().rate_limit_enabled:
            return
        ip = client_ip(request) or "unknown"
        if not await rate_limit.hit(redis, f"{name}:ip:{ip}", limit, window):
            raise _too_many(window)

    return dependency


def user_rate_limit(name: str, limit: int, window: int) -> Callable[..., Awaitable[None]]:
    async def dependency(
        user: User = Depends(get_current_user), redis: Redis = Depends(get_redis)
    ) -> None:
        if not get_settings().rate_limit_enabled:
            return
        if not await rate_limit.hit(redis, f"{name}:user:{user.id}", limit, window):
            raise _too_many(window)

    return dependency


async def admin_rate_limit(
    admin: User = Depends(get_current_admin), redis: Redis = Depends(get_redis)
) -> None:
    if not get_settings().rate_limit_enabled:
        return
    if not await rate_limit.hit(redis, f"admin:user:{admin.id}", 60, 60):
        raise _too_many(60)
