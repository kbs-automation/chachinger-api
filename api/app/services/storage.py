"""Avatar storage: private S3 bucket with presigned URLs, or local disk for development."""

import uuid
from functools import lru_cache
from pathlib import Path

import anyio

from app.core.config import get_settings
from app.services.errors import DomainError

MAX_AVATAR_BYTES = 5 * 1024 * 1024
CONTENT_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


def detect_image_type(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


@lru_cache
def _s3_client():
    import boto3

    return boto3.client("s3", region_name=get_settings().aws_region)


def validate_avatar(data: bytes) -> str:
    if len(data) > MAX_AVATAR_BYTES:
        raise DomainError(413, "avatar_too_large", "Avatar must be 5MB or smaller")
    ext = detect_image_type(data)
    if ext is None:
        raise DomainError(415, "unsupported_image", "Avatar must be JPEG, PNG or WebP")
    return ext


async def save_avatar(user_id: uuid.UUID, data: bytes) -> str:
    ext = validate_avatar(data)
    key = f"avatars/{user_id}/{uuid.uuid4().hex}.{ext}"
    settings = get_settings()
    if settings.storage_backend == "local":
        path = Path(settings.local_media_dir) / key
        await anyio.to_thread.run_sync(lambda: path.parent.mkdir(parents=True, exist_ok=True))
        await anyio.Path(path).write_bytes(data)
        return key
    await anyio.to_thread.run_sync(
        lambda: _s3_client().put_object(
            Bucket=settings.aws_s3_bucket,
            Key=key,
            Body=data,
            ContentType=CONTENT_TYPES[ext],
            ServerSideEncryption="AES256",
        )
    )
    return key


def avatar_url(key: str | None) -> str | None:
    if not key:
        return None
    settings = get_settings()
    if settings.storage_backend == "local":
        return f"/media/{key}"
    return _s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.aws_s3_bucket, "Key": key},
        ExpiresIn=settings.avatar_url_ttl_seconds,
    )
