"""Admin operations. Every write records an admin_audit_log row in the same transaction."""

import hashlib
import json
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import STARTED_AT, latency, uptime_seconds
from app.engine import mode_engine, zone_maps
from app.models import AdminAuditLog, EngineConfig, GameSession, P1ModeConfig, Play, Spin, User
from app.services import audit, billing, engine_config
from app.services.errors import DomainError, not_found


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def user_status(user: User) -> str:
    if user.deleted_at is not None:
        return "deleted"
    if user.is_suspended:
        return "suspended"
    if user.is_flagged:
        return "flagged"
    return "active"


async def dashboard(db: AsyncSession) -> dict[str, Any]:
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    total_users = await db.scalar(
        select(func.count()).select_from(User).where(User.deleted_at.is_(None))
    )
    tier_counts = (
        await db.execute(
            select(User.tier, func.count())
            .where(User.subscription_status == "active", User.deleted_at.is_(None))
            .group_by(User.tier)
        )
    ).all()
    trialing = await db.scalar(
        select(func.count()).select_from(User).where(User.subscription_status == "trialing")
    )
    mrr_cents = sum(billing.PRICE_CENTS.get(tier, 0) * count for tier, count in tier_counts)
    active_now = await db.scalar(
        select(func.count()).select_from(GameSession).where(GameSession.status == "active")
    )
    sessions_today = await db.scalar(
        select(func.count()).select_from(GameSession).where(GameSession.started_at >= today)
    )
    return {
        "total_users": int(total_users or 0),
        "active_subscribers": int(sum(c for _, c in tier_counts)),
        "trialing_subscribers": int(trialing or 0),
        "subscribers_by_tier": {tier: int(c) for tier, c in tier_counts},
        "mrr": round(mrr_cents / 100, 2),
        "active_sessions_now": int(active_now or 0),
        "sessions_today": int(sessions_today or 0),
        "engine_started_at": STARTED_AT,
        "engine_uptime_seconds": uptime_seconds(),
    }


async def list_users(
    db: AsyncSession, page: int, page_size: int, q: str | None, flagged: bool | None
) -> tuple[list[dict[str, Any]], int]:
    last_session = (
        select(func.max(GameSession.started_at))
        .where(GameSession.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    last_grade = (
        select(GameSession.execution_grade)
        .where(GameSession.user_id == User.id, GameSession.execution_grade.is_not(None))
        .order_by(GameSession.started_at.desc())
        .limit(1)
        .correlate(User)
        .scalar_subquery()
    )
    filters = []
    if q:
        like = f"%{q.lower()}%"
        filters.append(
            func.lower(User.email).like(like)
            | func.lower(func.coalesce(User.username, "")).like(like)
            | User.player_number.like(f"%{q}%")
        )
    if flagged is not None:
        filters.append(User.is_flagged.is_(flagged))
    total = await db.scalar(select(func.count()).select_from(User).where(*filters))
    rows = (
        await db.execute(
            select(User, last_session.label("last_session_at"), last_grade.label("grade"))
            .where(*filters)
            .order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    items = [
        {
            "id": u.id,
            "player_number": u.player_number,
            "username": u.display_name,
            "email": u.email,
            "tier": u.tier,
            "subscription_status": u.subscription_status,
            "joined_at": u.created_at,
            "last_session_at": last_at,
            "execution_grade": grade,
            "status": user_status(u),
            "is_flagged": u.is_flagged,
            "is_suspended": u.is_suspended,
        }
        for u, last_at, grade in rows
    ]
    return items, int(total or 0)


async def _get_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise not_found("user")
    return user


async def toggle_flag(db: AsyncSession, admin: User, user_id: uuid.UUID, ip: str | None) -> User:
    user = await _get_user(db, user_id)
    before = {"is_flagged": user.is_flagged}
    user.is_flagged = not user.is_flagged
    await audit.record_admin_action(
        db,
        admin,
        "FLAG" if user.is_flagged else "UNFLAG",
        "user",
        str(user.id),
        {"before": before, "after": {"is_flagged": user.is_flagged}},
        ip,
    )
    await db.commit()
    return user


async def set_suspended(
    db: AsyncSession,
    admin: User,
    user_id: uuid.UUID,
    suspended: bool,
    reason: str | None,
    ip: str | None,
) -> User:
    user = await _get_user(db, user_id)
    if user.id == admin.id and suspended:
        raise DomainError(422, "cannot_suspend_self", "Admins cannot suspend themselves")
    before = {"is_suspended": user.is_suspended}
    user.is_suspended = suspended
    await audit.record_admin_action(
        db,
        admin,
        "SUSPEND" if suspended else "UNSUSPEND",
        "user",
        str(user.id),
        {"before": before, "after": {"is_suspended": suspended}, "reason": reason},
        ip,
    )
    await db.commit()
    return user


async def session_detail(db: AsyncSession, session_id: uuid.UUID) -> dict[str, Any]:
    session = await db.get(GameSession, session_id)
    if session is None:
        raise not_found("session")
    user = await db.get(User, session.user_id)
    plays = list(
        await db.scalars(
            select(Play)
            .where(Play.session_id == session.id)
            .order_by(Play.cycle_number, Play.play_number)
        )
    )
    spins_by_play: dict[uuid.UUID, list[Spin]] = {p.id: [] for p in plays}
    if plays:
        spins = await db.scalars(
            select(Spin)
            .where(Spin.play_id.in_(list(spins_by_play)))
            .order_by(Spin.play_id, Spin.click_number)
        )
        for s in spins:
            spins_by_play[s.play_id].append(s)
    return {
        "session": session,
        "user": {
            "id": user.id if user else None,
            "player_number": user.player_number if user else None,
            "username": user.display_name if user else None,
            "email": user.email if user else None,
        },
        "plays": [{"play": p, "spins": spins_by_play[p.id]} for p in plays],
    }


async def live_sessions(db: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(GameSession, User, Play)
            .join(User, User.id == GameSession.user_id)
            .outerjoin(Play, and_(Play.session_id == GameSession.id, Play.status == "active"))
            .where(GameSession.status == "active")
            .order_by(GameSession.started_at.desc())
        )
    ).all()
    return [
        {
            "session_id": s.id,
            "user_id": u.id,
            "player_number": u.player_number,
            "username": u.display_name,
            "p1_mode": s.p1_mode,
            "session_budget": s.session_budget,
            "current_balance": s.current_balance,
            "total_wagered": s.total_wagered,
            "play_count": s.play_count,
            "play_id": p.id if p else None,
            "play_number": p.play_number if p else None,
            "cycle_number": p.cycle_number if p else s.cycle_number,
            "click_number": p.total_clicks if p else None,
            "click_cap": p.click_cap if p else None,
            "p1_mode_active": p.p1_mode_active if p else False,
            "started_at": s.started_at,
        }
        for s, u, p in rows
    ]


async def engine_health(db: AsyncSession, redis: Redis) -> dict[str, Any]:
    t0 = time.perf_counter()
    db_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    db_ms = round((time.perf_counter() - t0) * 1000, 2)

    t0 = time.perf_counter()
    try:
        redis_ok = bool(await redis.ping())
    except Exception:
        redis_ok = False
    redis_ms = round((time.perf_counter() - t0) * 1000, 2)

    configs = list(await db.scalars(select(P1ModeConfig).order_by(P1ModeConfig.sort_order)))
    modes = []
    for c in configs:
        errors = mode_engine.validate_zone_map(c.zone_map, c.click_cap)
        covered = sum(int(z["e"]) - int(z["s"]) + 1 for z in c.zone_map) if not errors else None
        modes.append(
            {
                "mode_id": c.mode_id,
                "is_active": c.is_active,
                "click_cap": c.click_cap,
                "zone_count": len(c.zone_map) if isinstance(c.zone_map, list) else 0,
                "covered_clicks": covered,
                "valid": not errors,
                "errors": errors,
            }
        )
    standard_errors = mode_engine.validate_zone_map(
        zone_maps.ENTERTAINMENT_ZONES, zone_maps.P1_UNIVERSAL_CLICK_CAP
    )
    healthy = db_ok and redis_ok and not standard_errors and all(m["valid"] for m in modes)
    return {
        "status": "ok" if healthy else "degraded",
        "mode_config_count": len(configs),
        "modes": modes,
        "standard_map_valid": not standard_errors,
        "database": {"ok": db_ok, "latency_ms": db_ms},
        "redis": {"ok": redis_ok, "latency_ms": redis_ms},
        "api_latency": latency.snapshot(),
        "uptime_seconds": uptime_seconds(),
    }


def _mode_snapshot(c: P1ModeConfig) -> dict[str, Any]:
    return _json_safe(
        {
            "label": c.label,
            "is_active": c.is_active,
            "min_budget": c.min_budget,
            "baseline_base": c.baseline_base,
            "baseline_press": c.baseline_press,
            "baseline_max": c.baseline_max,
            "zone_map": c.zone_map,
        }
    )


async def list_modes(db: AsyncSession) -> list[P1ModeConfig]:
    return list(await db.scalars(select(P1ModeConfig).order_by(P1ModeConfig.sort_order)))


async def update_mode(
    db: AsyncSession, admin: User, mode_id: str, changes: dict[str, Any], ip: str | None
) -> P1ModeConfig:
    if not changes:
        raise DomainError(422, "empty_update", "No changes supplied")
    config = await db.scalar(
        select(P1ModeConfig).where(P1ModeConfig.mode_id == mode_id).with_for_update()
    )
    if config is None:
        raise not_found("mode")
    before = _mode_snapshot(config)

    if "zone_map" in changes:
        zones = [dict(z) for z in changes["zone_map"]]
        errors = mode_engine.validate_zone_map(zones, config.click_cap)
        if errors:
            raise DomainError(422, "invalid_zone_map", "Zone map is invalid", {"errors": errors})
        config.zone_map = zones
    for field in (
        "label",
        "is_active",
        "min_budget",
        "baseline_base",
        "baseline_press",
        "baseline_max",
    ):
        if field in changes:
            setattr(config, field, changes[field])

    baselines = (config.baseline_base, config.baseline_press, config.baseline_max)
    if any(b is not None for b in baselines):
        if any(b is None for b in baselines):
            raise DomainError(422, "invalid_baselines", "Set all three baselines or none")
        if not baselines[0] <= baselines[1] <= baselines[2]:
            raise DomainError(422, "invalid_baselines", "Baselines must satisfy base ≤ press ≤ max")

    await audit.record_admin_action(
        db,
        admin,
        "MODE_UPDATE",
        "mode",
        mode_id,
        {"before": before, "after": _mode_snapshot(config)},
        ip,
    )
    await db.commit()
    return config


async def update_config(
    db: AsyncSession, admin: User, values: dict[str, Any], ip: str | None
) -> dict[str, Any]:
    validated = engine_config.validate_updates(values)
    before = await engine_config.get_all(db)
    for key, value in validated.items():
        row = await db.get(EngineConfig, key, with_for_update=True)
        if row is None:
            db.add(EngineConfig(key=key, value=value, updated_by=admin.id))
        else:
            row.value = value
            row.updated_by = admin.id
    await db.flush()
    after = {**before, **validated}
    await audit.record_admin_action(
        db,
        admin,
        "CONFIG_UPDATE",
        "config",
        ",".join(sorted(validated))[:64],
        {"before": before, "after": after},
        ip,
    )
    await db.commit()
    return after


def _redact_zone_maps(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k == "zone_map" and isinstance(v, list):
                digest = hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest()
                out[k] = {"redacted": True, "zone_count": len(v), "sha256": digest}
            else:
                out[k] = _redact_zone_maps(v)
        return out
    if isinstance(value, list):
        return [_redact_zone_maps(v) for v in value]
    return value


async def list_audit_log(
    db: AsyncSession, page: int, page_size: int, action: str | None, target_type: str | None
) -> tuple[list[dict[str, Any]], int]:
    filters = []
    if action:
        filters.append(AdminAuditLog.action == action)
    if target_type:
        filters.append(AdminAuditLog.target_type == target_type)
    total = await db.scalar(select(func.count()).select_from(AdminAuditLog).where(*filters))
    rows = await db.scalars(
        select(AdminAuditLog)
        .where(*filters)
        .order_by(AdminAuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        {
            "id": r.id,
            "admin_user_id": r.admin_user_id,
            "action": r.action,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "payload": _redact_zone_maps(r.payload),
            "ip_address": str(r.ip_address) if r.ip_address else None,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    return items, int(total or 0)
