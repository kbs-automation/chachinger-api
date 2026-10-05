"""Full 96-click exposure and server-authoritative Session Budget management."""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.engine import mode_engine, postures, ru_calc
from app.models import GameSession, P1ModeConfig
from app.services.errors import DomainError, not_found

ZERO = Decimal("0")


@dataclass(frozen=True)
class Exposure:
    exposure: Decimal
    required_budget: Decimal


@dataclass(frozen=True)
class RecalcResult:
    required_budget: Decimal
    adjusted: bool
    new_budget: Decimal
    current_balance: Decimal
    exposure: Decimal


def map_exposure(
    config: P1ModeConfig,
    base: Decimal,
    press: Decimal,
    max_bet: Decimal,
    active: tuple[str, ...] = postures.POSTURE_ORDER,
) -> Decimal:
    return mode_engine.zone_exposure(
        config.zone_map, *postures.effective_amounts(base, press, max_bet, active)
    )


def exposure_for_config(
    config: P1ModeConfig,
    base: Decimal,
    press: Decimal,
    max_bet: Decimal,
    active: tuple[str, ...] = postures.POSTURE_ORDER,
) -> Exposure:
    total = map_exposure(config, base, press, max_bet, active)
    return Exposure(exposure=total, required_budget=max(total, config.min_budget or ZERO))


async def calc_96_exposure(
    db: AsyncSession,
    mode_id: str,
    base: Decimal,
    press: Decimal,
    max_bet: Decimal,
    active: tuple[str, ...] = postures.POSTURE_ORDER,
) -> Exposure:
    config = await mode_engine.get_mode_config(db, mode_id)
    if config is None:
        raise not_found("mode")
    return exposure_for_config(config, base, press, max_bet, active)


def suggest_bets(config: P1ModeConfig, budget: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """RU bets for flexible modes; baselines scaled up (never down) for min-budget modes."""
    if config.baseline_base is None or config.baseline_press is None or config.baseline_max is None:
        return ru_calc.calc_ru_bets(budget)
    baseline_exposure = mode_engine.zone_exposure(
        config.zone_map, config.baseline_base, config.baseline_press, config.baseline_max
    )
    factor = max(Decimal("1"), budget / baseline_exposure) if baseline_exposure > 0 else Decimal(1)
    return (
        ru_calc.money_down(config.baseline_base * factor),
        ru_calc.money_down(config.baseline_press * factor),
        ru_calc.money_down(config.baseline_max * factor),
    )


def opening_budget(config: P1ModeConfig, requested: Decimal) -> Decimal:
    base, press, max_bet = suggest_bets(config, requested)
    return max(requested, exposure_for_config(config, base, press, max_bet).required_budget)


@dataclass(frozen=True)
class Suggestion:
    base: Decimal
    press: Decimal
    max: Decimal
    session_budget: Decimal


async def suggest_for_mode(db: AsyncSession, mode_id: str, requested: Decimal) -> Suggestion:
    config = await mode_engine.get_mode_config(db, mode_id)
    if config is None:
        raise not_found("mode")
    base, press, max_bet = suggest_bets(config, requested)
    return Suggestion(base, press, max_bet, opening_budget(config, requested))


def p1_budget_target(
    config: P1ModeConfig,
    player_budget: Decimal,
    base: Decimal,
    press: Decimal,
    max_bet: Decimal,
    active: tuple[str, ...],
) -> Decimal:
    """The Session Budget Play-1 needs for these bets.

    The suggested ladder with every posture active keeps the player's budget and the
    mode minimum as floors. Bets entered by hand, or played with a posture switched
    off, cost exactly their 96-click exposure, so the budget can fall as well as rise.
    """
    exposure = map_exposure(config, base, press, max_bet, active)
    min_budget = config.min_budget or ZERO
    by_hand = (base, press, max_bet) != suggest_bets(config, player_budget)
    if by_hand or len(active) < len(postures.POSTURE_ORDER):
        return exposure
    player_floor = player_budget if player_budget > min_budget else ZERO
    return max(player_floor, min_budget, exposure)


async def recalculate_session_budget(
    db: AsyncSession,
    session: GameSession,
    base: Decimal,
    press: Decimal,
    max_bet: Decimal,
    active: tuple[str, ...] = postures.POSTURE_ORDER,
) -> RecalcResult:
    if session.status != "active":
        raise DomainError(409, "session_not_active", "Session is not active")
    config = await mode_engine.get_mode_config(db, session.p1_mode)
    if config is None:
        raise not_found("mode")
    exposure = map_exposure(config, base, press, max_bet, active)
    if session.play_count == 0:
        player_budget = session.player_budget or session.session_budget
        target = p1_budget_target(config, player_budget, base, press, max_bet, active)
        required = target
    else:
        # Once Play-1 has started the budget can only grow.
        required = max(exposure, config.min_budget or ZERO)
        target = max(required, session.session_budget)
    adjusted = target != session.session_budget
    if adjusted:
        delta = target - session.session_budget
        session.session_budget = target
        session.current_balance = session.current_balance + delta
    return RecalcResult(
        required_budget=required,
        adjusted=adjusted,
        new_budget=session.session_budget,
        current_balance=session.current_balance,
        exposure=exposure,
    )
