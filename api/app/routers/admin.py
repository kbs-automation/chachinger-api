import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.redis import get_redis
from app.core.security import create_admin_token
from app.dependencies import admin_rate_limit, client_ip, get_current_admin, ip_rate_limit
from app.models import User
from app.schemas.admin import (
    AdminLoginRequest,
    AdminModeOut,
    AdminPlayOut,
    AdminSessionDetail,
    AdminSessionOut,
    AdminSpinOut,
    AdminTokenResponse,
    AdminUserRow,
    AdminUserStatus,
    AuditLogOut,
    ConfigUpdateRequest,
    DashboardOut,
    EngineConfigOut,
    LiveSessionOut,
    ModeUpdateRequest,
    SuspendRequest,
)
from app.schemas.common import P1ModeId, Page
from app.services import admin as admin_service
from app.services import auth as auth_service
from app.services import engine_config
from app.services.errors import DomainError

auth_router = APIRouter(prefix="/admin/auth", tags=["admin"])
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(admin_rate_limit)])


def _mode_out(c) -> AdminModeOut:
    return AdminModeOut(
        mode_id=c.mode_id,
        label=c.label,
        sort_order=c.sort_order,
        click_cap=c.click_cap,
        min_budget=c.min_budget,
        baseline_base=c.baseline_base,
        baseline_press=c.baseline_press,
        baseline_max=c.baseline_max,
        is_active=c.is_active,
        zone_count=len(c.zone_map) if isinstance(c.zone_map, list) else 0,
    )


@auth_router.post(
    "/login",
    response_model=AdminTokenResponse,
    dependencies=[Depends(ip_rate_limit("admin_login", 5, 900))],
)
async def admin_login(
    body: AdminLoginRequest, db: AsyncSession = Depends(get_db)
) -> AdminTokenResponse:
    user = await auth_service.authenticate(db, body.email, body.password)
    if not user.is_admin:
        raise DomainError(403, "forbidden", "Admin only")
    await db.commit()
    return AdminTokenResponse(
        access_token=create_admin_token(user.id),
        expires_in=get_settings().admin_token_ttl_minutes * 60,
    )


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(
    _: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)
) -> DashboardOut:
    return DashboardOut(**await admin_service.dashboard(db))


@router.get("/users", response_model=Page[AdminUserRow])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    q: str | None = Query(None, max_length=255),
    flagged: bool | None = None,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> Page[AdminUserRow]:
    items, total = await admin_service.list_users(db, page, page_size, q, flagged)
    return Page[AdminUserRow](
        items=[AdminUserRow(**i) for i in items], total=total, page=page, page_size=page_size
    )


@router.patch("/users/{user_id}/flag", response_model=AdminUserStatus)
async def flag_user(
    user_id: uuid.UUID,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUserStatus:
    user = await admin_service.toggle_flag(db, admin, user_id, client_ip(request))
    return AdminUserStatus.model_validate(user)


@router.patch("/users/{user_id}/suspend", response_model=AdminUserStatus)
async def suspend_user(
    user_id: uuid.UUID,
    request: Request,
    body: SuspendRequest | None = None,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> AdminUserStatus:
    body = body or SuspendRequest()
    user = await admin_service.set_suspended(
        db, admin, user_id, body.suspended, body.reason, client_ip(request)
    )
    if user.is_suspended:
        await auth_service.revoke_all(redis, str(user.id))
    return AdminUserStatus.model_validate(user)


@router.get("/sessions/{session_id}", response_model=AdminSessionDetail)
async def session_detail(
    session_id: uuid.UUID,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminSessionDetail:
    detail = await admin_service.session_detail(db, session_id)
    plays = []
    for entry in detail["plays"]:
        p = entry["play"]
        plays.append(
            AdminPlayOut(
                id=p.id,
                play_number=p.play_number,
                cycle_number=p.cycle_number,
                p1_mode=p.p1_mode,
                p1_mode_active=p.p1_mode_active,
                click_number=p.total_clicks,
                click_cap=p.click_cap,
                confirmed_base=p.confirmed_base,
                confirmed_press=p.confirmed_press,
                confirmed_max=p.confirmed_max,
                qualifying_result=p.qualifying_result,
                result_type=p.result_type,
                win_amount=p.win_amount,
                status=p.status,
                started_at=p.started_at,
                ended_at=p.ended_at,
                spins=[AdminSpinOut.model_validate(s) for s in entry["spins"]],
            )
        )
    return AdminSessionDetail(
        session=AdminSessionOut.model_validate(detail["session"]),
        user=detail["user"],
        plays=plays,
    )


@router.get("/live", response_model=list[LiveSessionOut])
async def live(
    _: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)
) -> list[LiveSessionOut]:
    return [LiveSessionOut(**row) for row in await admin_service.live_sessions(db)]


@router.get("/engine/health")
async def engine_health(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict:
    return await admin_service.engine_health(db, redis)


@router.get("/modes", response_model=list[AdminModeOut])
async def list_modes(
    _: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)
) -> list[AdminModeOut]:
    return [_mode_out(c) for c in await admin_service.list_modes(db)]


@router.patch("/modes/{mode_id}", response_model=AdminModeOut)
async def update_mode(
    mode_id: P1ModeId,
    body: ModeUpdateRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminModeOut:
    changes = body.model_dump(exclude_unset=True)
    config = await admin_service.update_mode(db, admin, mode_id, changes, client_ip(request))
    return _mode_out(config)


@router.get("/config", response_model=EngineConfigOut)
async def get_config(
    _: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)
) -> EngineConfigOut:
    return EngineConfigOut(values=await engine_config.get_all(db))


@router.patch("/config", response_model=EngineConfigOut)
async def update_config(
    body: ConfigUpdateRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> EngineConfigOut:
    values = await admin_service.update_config(db, admin, body.values, client_ip(request))
    return EngineConfigOut(values=values)


@router.get("/audit-log", response_model=Page[AuditLogOut])
async def audit_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: str | None = Query(None, max_length=64),
    target_type: Literal["user", "session", "config", "mode", "subscription"] | None = None,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> Page[AuditLogOut]:
    items, total = await admin_service.list_audit_log(db, page, page_size, action, target_type)
    return Page[AuditLogOut](
        items=[AuditLogOut(**i) for i in items], total=total, page=page, page_size=page_size
    )
