"""play_number / cycle_number management and play creation."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine import mode_engine, zone_maps
from app.models import GameSession, Play
from app.services import budget
from app.services.errors import DomainError, not_found


async def active_play(db: AsyncSession, session_id) -> Play | None:
    return await db.scalar(
        select(Play).where(Play.session_id == session_id, Play.status == "active")
    )


async def latest_play(db: AsyncSession, session_id) -> Play | None:
    return await db.scalar(
        select(Play)
        .where(Play.session_id == session_id)
        .order_by(Play.cycle_number.desc(), Play.play_number.desc())
        .limit(1)
    )


def next_position(last: Play | None) -> tuple[int, int]:
    if last is None:
        return 1, 1
    play_number, cycle_number = last.play_number + 1, last.cycle_number
    if play_number > zone_maps.PLAYS_PER_CYCLE:
        return 1, cycle_number + 1
    return play_number, cycle_number


async def start_play(
    db: AsyncSession,
    session: GameSession,
    base: Decimal,
    press: Decimal,
    max_bet: Decimal,
) -> Play:
    if session.status != "active":
        raise DomainError(409, "session_not_active", "Session is not active")
    if await active_play(db, session.id) is not None:
        raise DomainError(409, "play_already_active", "Finish the current play first")

    last = await latest_play(db, session.id)
    play_number, cycle_number = next_position(last)

    if last is None:
        config = await mode_engine.get_mode_config(db, session.p1_mode)
        if config is None:
            raise not_found("mode")
        floors = (
            ("confirmed_base", base, config.baseline_base),
            ("confirmed_press", press, config.baseline_press),
            ("confirmed_max", max_bet, config.baseline_max),
        )
        for field, value, floor in floors:
            if floor is not None and value < floor:
                raise DomainError(
                    422,
                    "bet_below_mode_floor",
                    f"{field} is below the {config.label} floor",
                    {"field": field, "floor": float(floor)},
                )
        exposure = budget.exposure_for_config(config, base, press, max_bet)
        if exposure.required_budget > session.session_budget:
            raise DomainError(
                409,
                "budget_recalculation_required",
                "Bets need a larger Session Budget; call /recalculate-budget first",
                {"required_budget": float(exposure.required_budget)},
            )
        p1_mode: str | None = session.p1_mode
        p1_mode_active = session.p1_mode != "entertainment"
        click_cap = config.click_cap
    else:
        p1_mode, p1_mode_active, click_cap = None, False, zone_maps.P2_PLUS_CLICK_CAP

    play = Play(
        session_id=session.id,
        user_id=session.user_id,
        play_number=play_number,
        cycle_number=cycle_number,
        p1_mode=p1_mode,
        p1_mode_active=p1_mode_active,
        total_clicks=0,
        click_cap=click_cap,
        confirmed_base=base,
        confirmed_press=press,
        confirmed_max=max_bet,
        status="active",
    )
    db.add(play)
    session.play_count = (session.play_count or 0) + 1
    session.cycle_number = cycle_number
    session.confirmed_base = base
    session.confirmed_press = press
    session.confirmed_max = max_bet
    await db.flush()
    return play
