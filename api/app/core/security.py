import logging
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import bcrypt
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import get_settings

logger = logging.getLogger(__name__)

USER_ALGORITHM = "RS256"
ADMIN_ALGORITHM = "HS256"


class TokenError(Exception):
    pass


def hash_password(password: str) -> str:
    rounds = get_settings().bcrypt_rounds
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=rounds)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def generate_rsa_key_pair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return private_pem, public_pem


@lru_cache
def rsa_keys() -> tuple[str, str]:
    settings = get_settings()
    private_pem = settings.jwt_private_key.replace("\\n", "\n").strip()
    public_pem = settings.jwt_public_key.replace("\\n", "\n").strip()
    if private_pem and public_pem:
        return private_pem, public_pem
    if settings.is_production:
        raise RuntimeError("JWT_PRIVATE_KEY and JWT_PUBLIC_KEY must be set in production")
    logger.warning("JWT keys not configured; generating an ephemeral RS256 key pair")
    return generate_rsa_key_pair()


def check_admin_secret() -> None:
    settings = get_settings()
    secret = settings.admin_jwt_secret
    if settings.is_production and (len(secret) < 32 or secret == "change-me-admin-secret"):
        raise RuntimeError("ADMIN_JWT_SECRET must be a unique value of at least 32 bytes")


def _now() -> datetime:
    return datetime.now(UTC)


def create_access_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    now = _now()
    claims = {
        "sub": str(user_id),
        "type": "access",
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    return jwt.encode(claims, rsa_keys()[0], algorithm=USER_ALGORITHM)


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, str, int]:
    """Returns (token, jti, ttl_seconds)."""
    settings = get_settings()
    now = _now()
    ttl = timedelta(days=settings.refresh_token_ttl_days)
    jti = uuid.uuid4().hex
    claims = {"sub": str(user_id), "type": "refresh", "jti": jti, "iat": now, "exp": now + ttl}
    token = jwt.encode(claims, rsa_keys()[0], algorithm=USER_ALGORITHM)
    return token, jti, int(ttl.total_seconds())


def decode_user_token(token: str, expected_type: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            rsa_keys()[1],
            algorithms=[USER_ALGORITHM],
            options={"require": ["sub", "exp", "type", "jti"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    if claims.get("type") != expected_type:
        raise TokenError("wrong token type")
    return claims


def create_admin_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    now = _now()
    claims = {
        "sub": str(user_id),
        "type": "admin",
        "is_admin": True,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(minutes=settings.admin_token_ttl_minutes),
    }
    return jwt.encode(claims, settings.admin_jwt_secret, algorithm=ADMIN_ALGORITHM)


def decode_admin_token(token: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            get_settings().admin_jwt_secret,
            algorithms=[ADMIN_ALGORITHM],
            options={"require": ["sub", "exp", "type"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    if claims.get("type") != "admin" or claims.get("is_admin") is not True:
        raise TokenError("not an admin token")
    return claims
