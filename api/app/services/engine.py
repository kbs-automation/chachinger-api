"""Spin processing: posture lookup, hard exit enforcement, P1 mode deactivation."""

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine import early_attack, mode_engine, postures, ru_calc, zone_maps
from app.models import GameSession, Play, Spin
from app.models.base import utcnow
from app.services import engine_config
from app.services.errors import DomainError

QUALIFYING_MULTIPLIER = Decimal("10")
MIN_MULTIPLIER = Decimal("1.0")
MAX_MULTIPLIER = Decimal("10000.0")
RESULT_PATTERN = re.compile(r"^\d+(\.\d+)?x?$", re.IGNORECASE)
CENTS = Decimal("0.01")


@dataclass(frozen=True)
class SpinOutcome:
    spin: Spin | None
    posture: str
    bet_amount: Decimal
    progress_pct: int
    at_hard_exit_cap: bool
    redirect: str


@dataclass(frozen=True)
class ResultOutcome:
    qualifying: bool
    win_amount: Decimal
    multiplier: Decimal | None
    redirect: str


@dataclass(frozen=True)
class UndoOutcome:
    posture: str
    bet_amount: Decimal
    has_spins: bool
    progress_pct: int


def progress_pct(click: int, click_cap: int) -> int:
    if click_cap <= 0:
        return 0
    pct = (Decimal(click) / Decimal(click_cap) * 100).quantize(Decimal("1"), ROUND_HALF_UP)
    return int(pct)


async def get_posture(db: AsyncSession, play: Play, click: int) -> str:
    if play.p1_mode_active and play.p1_mode and play.p1_mode != "entertainment":
        zones = await mode_engine.load_zone_map(db, play.p1_mode)
    else:
        zones = zone_maps.ENTERTAINMENT_ZONES
    posture = postures.effective(
        mode_engine.posture_at(zones, click), postures.from_column(play.active_postures)
    )
    if early_attack.in_window(click) and await engine_config.get_value(db, "early_attack_enabled"):
        if early_attack.authorize(early_attack.EarlyAttackSignals(current_click=click)):
            return "early_attack"
    return posture


def bet_for_posture(play: Play, posture: str) -> Decimal:
    """Bets come only from the amounts locked on the play row (Rule 3)."""
    if posture == "max":
        return play.confirmed_max
    if posture == "press":
        return play.confirmed_press
    if posture == "early_attack":
        return ru_calc.money_down(play.confirmed_press * early_attack.SIZE_FACTOR)
    return play.confirmed_base


async def upcoming_bet(db: AsyncSession, play: Play) -> tuple[str, Decimal]:
    click = min(play.total_clicks + 1, play.click_cap)
    posture = await get_posture(db, play, click)
    return posture, bet_for_posture(play, posture)


async def compute_execution_grade(db: AsyncSession, session: GameSession) -> str:
    # Stub until the real grading algorithm is specified.
    return str(await engine_config.get_value(db, "execution_grade_default"))


def _end_play(play: Play, status: str, result_type: str) -> None:
    play.status = status
    play.result_type = result_type
    play.ended_at = utcnow()


async def _hard_exit(db: AsyncSession, play: Play, session: GameSession) -> None:
    _end_play(play, "hard_exit", "hard_exit")
    session.status = "hard_exit"
    session.ended_at = utcnow()
    session.execution_grade = await compute_execution_grade(db, session)


def _require_active(play: Play, session: GameSession) -> None:
    if session.status != "active":
        raise DomainError(409, "session_not_active", "Session is not active")
    if play.status != "active":
        raise DomainError(409, "play_not_active", "Play is not active", {"status": play.status})


async def process_spin(db: AsyncSession, play: Play, session: GameSession) -> SpinOutcome:
    _require_active(play, session)
    next_click = play.total_clicks + 1
    if next_click > play.click_cap:
        await _hard_exit(db, play, session)
        last_posture = await get_posture(db, play, play.click_cap)
        return SpinOutcome(None, last_posture, Decimal("0"), 100, True, "hard_exit")

    posture = await get_posture(db, play, next_click)
    bet = bet_for_posture(play, posture)
    spin = Spin(play_id=play.id, click_number=next_click, posture=posture, bet_amount=bet)
    db.add(spin)
    play.total_clicks = next_click
    session.current_balance = session.current_balance - bet
    session.total_wagered = session.total_wagered + bet
    return SpinOutcome(
        spin=spin,
        posture=posture,
        bet_amount=bet,
        progress_pct=progress_pct(next_click, play.click_cap),
        at_hard_exit_cap=next_click >= play.click_cap,
        redirect="continue",
    )


def parse_result(raw: str) -> tuple[str, Decimal | None]:
    value = raw.strip().lower()
    if value == "bonus":
        return "bonus", None
    if not RESULT_PATTERN.match(value):
        raise DomainError(
            422, "invalid_result", 'Result must be "bonus" or a multiplier like "34x"'
        )
    multiplier = Decimal(value.rstrip("x"))
    if not MIN_MULTIPLIER <= multiplier <= MAX_MULTIPLIER:
        raise DomainError(422, "invalid_result", "Multiplier must be between 1.0 and 10000.0")
    return "multiplier", multiplier


def multiplier_for_win(win: Decimal, bet: Decimal) -> Decimal:
    if bet <= 0:
        raise DomainError(422, "invalid_result", "This spin has no bet to measure a win against")
    multiplier = (win / bet).quantize(CENTS)
    if multiplier > MAX_MULTIPLIER:
        raise DomainError(422, "invalid_result", "Win is more than 10000x the bet")
    return multiplier


async def submit_result(
    db: AsyncSession,
    play: Play,
    session: GameSession,
    spin: Spin,
    raw_result: str | None,
    win_amount: Decimal | None = None,
) -> ResultOutcome:
    """raw_result is "34x" or "bonus"; without it win_amount is the dollar payout."""
    _require_active(play, session)
    if spin.result_input is not None:
        raise DomainError(409, "result_already_submitted", "A result was already submitted")
    if spin.click_number != play.total_clicks:
        raise DomainError(409, "stale_spin", "Results can only be submitted for the latest spin")

    if raw_result is None:
        if win_amount is None:
            raise DomainError(422, "invalid_result", "Provide a result or a win amount")
        kind = "multiplier"
        win = win_amount.quantize(CENTS)
        multiplier: Decimal | None = multiplier_for_win(win, spin.bet_amount)
        stored_input = f"{multiplier}x"
    else:
        kind, multiplier = parse_result(raw_result)
        if kind == "bonus":
            win = (win_amount or Decimal("0")).quantize(CENTS)
        else:
            assert multiplier is not None
            win = (spin.bet_amount * multiplier).quantize(CENTS)
        stored_input = raw_result.strip().lower()
    qualifying = kind == "bonus" or (multiplier is not None and multiplier >= QUALIFYING_MULTIPLIER)

    spin.result_input = stored_input[:20]
    spin.is_qualifying = qualifying
    session.current_balance = session.current_balance + win
    play.win_amount = play.win_amount + win

    if qualifying:
        _end_play(play, "completed", kind)
        play.qualifying_result = multiplier
        play.p1_mode_active = False
        return ResultOutcome(True, win, multiplier, "next_play")
    if spin.click_number >= play.click_cap:
        await _hard_exit(db, play, session)
        return ResultOutcome(False, win, multiplier, "hard_exit")
    return ResultOutcome(False, win, multiplier, "continue")


async def undo_last_spin(db: AsyncSession, play: Play, session: GameSession) -> UndoOutcome:
    """Reverses the latest spin of an active play, as if it was never registered."""
    _require_active(play, session)
    if play.total_clicks == 0:
        raise DomainError(409, "nothing_to_undo", "This play has no spins to undo")
    spin = await db.scalar(
        select(Spin)
        .where(Spin.play_id == play.id, Spin.click_number == play.total_clicks)
        .with_for_update()
    )
    if spin is None:
        raise DomainError(409, "nothing_to_undo", "This play has no spins to undo")
    if spin.result_input is not None:
        raise DomainError(409, "result_already_submitted", "A spin with a result cannot be undone")
    session.current_balance = session.current_balance + spin.bet_amount
    session.total_wagered = session.total_wagered - spin.bet_amount
    play.total_clicks = play.total_clicks - 1
    await db.delete(spin)

    shown_click = max(play.total_clicks, 1)
    posture = await get_posture(db, play, shown_click)
    return UndoOutcome(
        posture=posture,
        bet_amount=bet_for_posture(play, posture),
        has_spins=play.total_clicks > 0,
        progress_pct=progress_pct(play.total_clicks, play.click_cap),
    )


def end_play_manually(play: Play, session: GameSession) -> None:
    _require_active(play, session)
    _end_play(play, "manual_exit", "manual_exit")


async def end_session_manually(
    db: AsyncSession, session: GameSession, active_play: Play | None
) -> None:
    if session.status != "active":
        raise DomainError(409, "session_not_active", "Session is not active")
    if active_play is not None and active_play.status == "active":
        _end_play(active_play, "manual_exit", "manual_exit")
    session.status = "manual_exit"
    session.ended_at = utcnow()
    session.execution_grade = await compute_execution_grade(db, session)
