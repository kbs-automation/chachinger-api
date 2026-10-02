"""Registration, login, and rotating refresh tokens (JWT RS256, revocation state in Redis)."""

import secrets
import uuid
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_user_token,
    hash_password,
    verify_password,
)
from app.models import User
from app.models.base import utcnow
from app.services.errors import DomainError

# Equalizes login timing for unknown emails.
_DUMMY_HASH = hash_password(secrets.token_hex(8))


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_ttl: int


def _rt_key(jti: str) -> str:
    return f"rt:{jti}"


def _user_rt_key(user_id: str) -> str:
    return f"rt_user:{user_id}"


async def _username_taken(db: AsyncSession, username: str, exclude: uuid.UUID | None) -> bool:
    stmt = select(User.id).where(func.lower(User.username) == username.lower())
    if exclude is not None:
        stmt = stmt.where(User.id != exclude)
    return await db.scalar(stmt) is not None


async def generate_player_number(db: AsyncSession) -> str:
    for digits in (5, 5, 5, 5, 5, 6, 6, 7):
        candidate = f"#{secrets.randbelow(10**digits - 10 ** (digits - 1)) + 10 ** (digits - 1)}"
        if await db.scalar(select(User.id).where(User.player_number == candidate)) is None:
            return candidate
    raise DomainError(503, "player_number_exhausted", "Could not allocate a player number")


async def register_user(db: AsyncSession, email: str, password: str, username: str | None) -> User:
    email = email.strip().lower()
    if await db.scalar(select(User.id).where(User.email == email)) is not None:
        raise DomainError(409, "email_taken", "An account with this email already exists")
    if username and await _username_taken(db, username, None):
        raise DomainError(409, "username_taken", "Username is already taken")
    user = User(
        email=email,
        password_hash=hash_password(password),
        username=username or None,
        player_number=await generate_player_number(db),
        tier="vip",
        last_login_at=utcnow(),
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise DomainError(409, "account_conflict", "Email or username already in use") from exc
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User:
    user = await db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or user.deleted_at is not None:
        verify_password(password, _DUMMY_HASH)
        raise DomainError(401, "invalid_credentials", "Invalid email or password")
    if not verify_password(password, user.password_hash):
        raise DomainError(401, "invalid_credentials", "Invalid email or password")
    if user.is_suspended:
        raise DomainError(403, "account_suspended", "This account is suspended")
    user.last_login_at = utcnow()
    return user


async def issue_tokens(redis: Redis, user: User) -> TokenPair:
    settings = get_settings()
    refresh, jti, ttl = create_refresh_token(user.id)
    uid = str(user.id)
    async with redis.pipeline(transaction=True) as pipe:
        pipe.set(_rt_key(jti), uid, ex=ttl)
        pipe.sadd(_user_rt_key(uid), jti)
        pipe.expire(_user_rt_key(uid), ttl)
        await pipe.execute()
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=refresh,
        expires_in=settings.access_token_ttl_minutes * 60,
        refresh_ttl=ttl,
    )


async def revoke_all(redis: Redis, user_id: str) -> None:
    jtis = await redis.smembers(_user_rt_key(user_id))
    async with redis.pipeline(transaction=True) as pipe:
        for jti in jtis:
            pipe.delete(_rt_key(jti))
        pipe.delete(_user_rt_key(user_id))
        await pipe.execute()


async def rotate_refresh(db: AsyncSession, redis: Redis, token: str) -> tuple[User, TokenPair]:
    try:
        claims = decode_user_token(token, "refresh")
    except TokenError as exc:
        raise DomainError(401, "invalid_refresh_token", "Refresh token is invalid") from exc
    jti, uid = claims["jti"], claims["sub"]
    stored = await redis.getdel(_rt_key(jti))
    if stored is None:
        # A signed-but-unknown token was already rotated: treat as theft, revoke the family.
        await revoke_all(redis, uid)
        raise DomainError(401, "refresh_token_reused", "Refresh token is no longer valid")
    await redis.srem(_user_rt_key(uid), jti)
    user = await db.get(User, uuid.UUID(uid))
    if user is None or user.deleted_at is not None or user.is_suspended:
        await revoke_all(redis, uid)
        raise DomainError(401, "invalid_refresh_token", "Refresh token is invalid")
    return user, await issue_tokens(redis, user)


async def revoke_refresh(redis: Redis, token: str, user_id: str) -> None:
    try:
        claims = decode_user_token(token, "refresh")
    except TokenError:
        return
    if claims["sub"] != user_id:
        return
    await redis.delete(_rt_key(claims["jti"]))
    await redis.srem(_user_rt_key(user_id), claims["jti"])


async def update_username(db: AsyncSession, user: User, username: str) -> User:
    if await _username_taken(db, username, user.id):
        raise DomainError(409, "username_taken", "Username is already taken")
    user.username = username
    return user
