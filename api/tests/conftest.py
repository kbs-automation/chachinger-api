import os
import tempfile

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite://")
os.environ.update(
    {
        "ENVIRONMENT": "test",
        "DATABASE_URL": TEST_DATABASE_URL,
        "RATE_LIMIT_ENABLED": "false",
        "BCRYPT_ROUNDS": "4",
        "STORAGE_BACKEND": "local",
        "LOCAL_MEDIA_DIR": tempfile.mkdtemp(prefix="cha3535-media-"),
        "COOKIE_SECURE": "false",
        "STRIPE_WEBHOOK_SECRET": "whsec_test_secret",
        "STRIPE_BLACK_PRICE_ID": "price_black_test",
        "STRIPE_ELITE_PRICE_ID": "price_elite_test",
        "ADMIN_JWT_SECRET": "test-admin-secret-that-is-at-least-32-bytes",
        "CORS_ORIGINS": "http://localhost",
    }
)

import fakeredis  # noqa: E402
import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.db import get_db  # noqa: E402
from app.core.redis import get_redis  # noqa: E402
from app.engine.zone_maps import MODE_SEEDS  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, P1ModeConfig  # noqa: E402

if TEST_DATABASE_URL.startswith("sqlite"):
    test_engine = create_async_engine(
        TEST_DATABASE_URL, poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
else:
    test_engine = create_async_engine(TEST_DATABASE_URL)

TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


async def _override_get_db():
    async with TestSession() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@pytest.fixture(autouse=True)
async def fresh_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with TestSession() as session:
        session.add_all(P1ModeConfig(**seed) for seed in MODE_SEEDS)
        await session.commit()
    yield


@pytest.fixture
async def redis():
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    yield client
    await client.flushall()
    await client.aclose()


@pytest.fixture
async def client(redis):
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = lambda: redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def db():
    async with TestSession() as session:
        yield session
