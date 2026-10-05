import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine import mode_engine
from app.models import GameSession, User
from app.services import budget, engine_config
from app.services.errors import DomainError, not_found


@dataclass(frozen=True)
class CreatedSession:
    session: GameSession
    suggested_base: Decimal
    suggested_press: Decimal
    suggested_max: Decimal
    mode_click_cap: int


async def create_session(
    db: AsyncSession, user: User, p1_mode: str, requested_budget: Decimal
) -> CreatedSession:
    if await engine_config.get_value(db, "maintenance_mode"):
        raise DomainError(503, "maintenance_mode", "New sessions are temporarily disabled")

    config = await mode_engine.get_mode_config(db, p1_mode)
    if config is None or not config.is_active:
        raise DomainError(422, "mode_unavailable", f"Mode {p1_mode} is not available")
    if config.min_budget is not None and requested_budget < config.min_budget:
        raise DomainError(
            422,
            "budget_below_minimum",
            f"{config.label} requires a budget of at least {config.min_budget}",
            {"min_budget": float(config.min_budget)},
        )

    existing = await db.scalar(
        select(GameSession.id).where(GameSession.user_id == user.id, GameSession.status == "active")
    )
    if existing is not None:
        raise DomainError(
            409,
            "session_already_active",
            "End your active session first",
            {"session_id": str(existing)},
        )

    base, press, max_bet = budget.suggest_bets(config, requested_budget)
    session_budget = budget.opening_budget(config, requested_budget)

    session = GameSession(
        user_id=user.id,
        p1_mode=p1_mode,
        session_budget=session_budget,
        player_budget=requested_budget,
        current_balance=session_budget,
        confirmed_base=base,
        confirmed_press=press,
        confirmed_max=max_bet,
        status="active",
        play_count=0,
        cycle_number=1,
        total_wagered=Decimal("0"),
    )
    db.add(session)
    await db.flush()
    return CreatedSession(session, base, press, max_bet, config.click_cap)


async def get_owned_session(
    db: AsyncSession, user: User, session_id: uuid.UUID, for_update: bool = False
) -> GameSession:
    stmt = select(GameSession).where(GameSession.id == session_id, GameSession.user_id == user.id)
    if for_update:
        stmt = stmt.with_for_update()
    session = await db.scalar(stmt)
    if session is None:
        raise not_found("session")
    return session


async def discard_unplayed_session(db: AsyncSession, session: GameSession) -> None:
    """A session abandoned during bet setup leaves no history behind."""
    if session.status != "active":
        raise DomainError(409, "session_not_active", "Session is not active")
    if session.play_count:
        raise DomainError(
            409, "session_has_plays", "A session with plays must be ended, not discarded"
        )
    await db.delete(session)


async def list_sessions(
    db: AsyncSession, user: User, page: int, page_size: int, status: str | None
) -> tuple[list[GameSession], int]:
    filters = [GameSession.user_id == user.id]
    if status:
        filters.append(GameSession.status == status)
    total = await db.scalar(select(func.count()).select_from(GameSession).where(*filters))
    rows = await db.scalars(
        select(GameSession)
        .where(*filters)
        .order_by(GameSession.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows), int(total or 0)
