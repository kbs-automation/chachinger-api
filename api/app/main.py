import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.db import engine
from app.core.metrics import latency
from app.core.redis import close_redis
from app.core.security import check_admin_secret, rsa_keys
from app.routers import admin, auth, billing, modes, plays, sessions, spins, users
from app.services.errors import DomainError

API_PREFIX = "/api/v1"

settings = get_settings()
logging.basicConfig(level=logging.INFO)

if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn, environment=settings.environment, traces_sample_rate=0.1
    )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    rsa_keys()
    check_admin_secret()
    yield
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title="CHA3535 Session Intelligence API",
    version="3.0.0",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Stripe-Signature"],
)


@app.middleware("http")
async def track_latency(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    latency.record((time.perf_counter() - start) * 1000)
    return response


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.to_detail()})


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


for r in (
    auth.router,
    sessions.router,
    plays.router,
    spins.router,
    modes.router,
    users.router,
    billing.router,
    billing.webhook_router,
    admin.auth_router,
    admin.router,
):
    app.include_router(r, prefix=API_PREFIX)

if settings.storage_backend == "local":
    media_dir = Path(settings.local_media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=media_dir), name="media")
