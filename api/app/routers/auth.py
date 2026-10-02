from fastapi import APIRouter, Depends, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.redis import get_redis
from app.dependencies import get_current_user, ip_rate_limit
from app.models import User
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserProfile,
)
from app.schemas.common import MessageResponse
from app.serializers import to_profile
from app.services import auth as auth_service
from app.services.auth import TokenPair
from app.services.errors import DomainError

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, tokens: TokenPair) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.refresh_cookie_name,
        tokens.refresh_token,
        max_age=tokens.refresh_ttl,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=COOKIE_PATH,
    )


def _refresh_token_from(request: Request, body: RefreshRequest | None) -> str | None:
    if body is not None and body.refresh_token:
        return body.refresh_token
    return request.cookies.get(get_settings().refresh_cookie_name)


def _auth_response(user: User, tokens: TokenPair) -> AuthResponse:
    return AuthResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        user=to_profile(user),
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(ip_rate_limit("register", 10, 3600))],
)
async def register(
    body: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AuthResponse:
    user = await auth_service.register_user(db, body.email, body.password, body.username)
    await db.commit()
    tokens = await auth_service.issue_tokens(redis, user)
    _set_refresh_cookie(response, tokens)
    return _auth_response(user, tokens)


@router.post(
    "/login",
    response_model=AuthResponse,
    dependencies=[Depends(ip_rate_limit("login", 5, 900))],
)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AuthResponse:
    user = await auth_service.authenticate(db, body.email, body.password)
    await db.commit()
    tokens = await auth_service.issue_tokens(redis, user)
    _set_refresh_cookie(response, tokens)
    return _auth_response(user, tokens)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> TokenResponse:
    token = _refresh_token_from(request, body)
    if not token:
        raise DomainError(401, "missing_refresh_token", "Refresh token is required")
    _, tokens = await auth_service.rotate_refresh(db, redis, token)
    _set_refresh_cookie(response, tokens)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
) -> MessageResponse:
    token = _refresh_token_from(request, body)
    if token:
        await auth_service.revoke_refresh(redis, token, str(user.id))
    else:
        await auth_service.revoke_all(redis, str(user.id))
    response.delete_cookie(get_settings().refresh_cookie_name, path=COOKIE_PATH)
    return MessageResponse(status="logged_out")


@router.get("/me", response_model=UserProfile)
async def me(user: User = Depends(get_current_user)) -> UserProfile:
    return to_profile(user)
