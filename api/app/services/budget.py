"""Full 96-click exposure and server-authoritative Session Budget management."""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.engine import mode_engine, ru_calc
from app.models import GameSession, P1ModeConfig
from app.services.errors import DomainError, not_found


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


def exposure_for_config(
    config: P1ModeConfig, base: Decimal, press: Decimal, max_bet: Decimal
) -> Exposure:
    total = mode_engine.zone_exposure(config.zone_map, base, press, max_bet)
    return Exposure(exposure=total, required_budget=max(total, config.min_budget or Decimal("0")))


async def calc_96_exposure(
    db: AsyncSession, mode_id: str, base: Decimal, press: Decimal, max_bet: Decimal
) -> Exposure:
    config = await mode_engine.get_mode_config(db, mode_id)
    if config is None:
        raise not_found("mode")
    return exposure_for_config(config, base, press, max_bet)


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


async def recalculate_session_budget(
    db: AsyncSession, session: GameSession, base: Decimal, press: Decimal, max_bet: Decimal
) -> RecalcResult:
    if session.status != "active":
        raise DomainError(409, "session_not_active", "Session is not active")
    result = await calc_96_exposure(db, session.p1_mode, base, press, max_bet)
    adjusted = result.required_budget > session.session_budget
    if adjusted:
        delta = result.required_budget - session.session_budget
        session.session_budget = result.required_budget
        session.current_balance = session.current_balance + delta
    return RecalcResult(
        required_budget=result.required_budget,
        adjusted=adjusted,
        new_budget=session.session_budget,
        current_balance=session.current_balance,
        exposure=result.exposure,
    )
