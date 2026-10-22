"""Pocket-route offer for the Play Complete screen. Click bounds never leave this layer."""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.engine import postures, routes
from app.models import GameSession
from app.services import play_tracker
from app.services.errors import DomainError


@dataclass(frozen=True)
class RouteCard:
    route_id: str
    heading: str
    detail: str
    exposure_pct: float
    risk_pct: float


@dataclass(frozen=True)
class RouteReference:
    budget: Decimal
    base: Decimal
    press: Decimal
    max: Decimal
    source: str
    below_base: Decimal | None = None


@dataclass(frozen=True)
class Continuation:
    can_continue: bool
    block_reason: str | None
    completed_play_number: int | None
    next_play_number: int | None
    next_cycle_number: int | None
    prompt: str | None
    selected_route: str | None
    reference: RouteReference | None
    routes: tuple[RouteCard, ...]


def _cards(
    budget: Decimal,
    balance: Decimal,
    base: Decimal,
    press: Decimal,
    max_bet: Decimal,
    active: tuple[str, ...],
    below_base: Decimal | None = None,
) -> tuple[RouteCard, ...]:
    cards: list[RouteCard] = []
    for route in routes.ROUTES:
        wager = routes.route_wager(route.route_id, base, press, max_bet, active, below_base)
        cards.append(
            RouteCard(
                route_id=route.route_id,
                heading=routes.heading(route),
                detail=routes.detail(route),
                exposure_pct=routes.percent(wager, budget),
                risk_pct=routes.percent(wager, balance),
            )
        )
    return tuple(cards)


async def describe(
    db: AsyncSession,
    session: GameSession,
    *,
    budget: Decimal | None = None,
    base: Decimal | None = None,
    press: Decimal | None = None,
    max_bet: Decimal | None = None,
    active: tuple[str, ...] | None = None,
    below_base: Decimal | None = None,
) -> Continuation:
    """Routes the engine will accept for the next play, priced for the given ladder.

    With no ladder, the reference is the session budget and its Risk Unit bets.
    """
    if session.status == "hard_exit":
        return _blocked("hard_exit")
    if session.status != "active":
        return _blocked("session_not_active")
    if await play_tracker.active_play(db, session.id) is not None:
        return _blocked("play_in_progress")
    latest = await play_tracker.latest_play(db, session.id)
    if latest is None or latest.status not in ("completed", "manual_exit"):
        return _blocked("no_completed_play")
    if session.current_balance <= 0:
        return _blocked("insufficient_balance")

    next_play, next_cycle = play_tracker.next_position(latest)
    priced_budget = session.session_budget if budget is None else budget
    if base is None or press is None or max_bet is None:
        base, press, max_bet = routes.reference_ladder(priced_budget)
        source = "session_budget" if budget is None else "quoted_bets"
    else:
        source = "quoted_bets"
    chosen = active or postures.chosen(None, below_base)
    if below_base is not None and below_base > base:
        raise DomainError(
            422,
            "invalid_ladder",
            "active bets must satisfy below_base ≤ base ≤ press ≤ max",
        )
    return Continuation(
        can_continue=True,
        block_reason=None,
        completed_play_number=latest.play_number,
        next_play_number=next_play,
        next_cycle_number=next_cycle,
        prompt=f"Choose Play-{next_play} Budget",
        selected_route=session.pending_route,
        reference=RouteReference(priced_budget, base, press, max_bet, source, below_base),
        routes=_cards(
            priced_budget, session.current_balance, base, press, max_bet, chosen, below_base
        ),
    )


def _blocked(reason: str) -> Continuation:
    return Continuation(False, reason, None, None, None, None, None, None, ())


async def select_route(db: AsyncSession, session: GameSession, route_id: str) -> Continuation:
    if routes.get_route(route_id) is None:
        raise DomainError(422, "route_unavailable", "That route is not available")
    view = await describe(db, session)
    if not view.can_continue:
        raise DomainError(
            409,
            "continuation_unavailable",
            "The next play cannot be started",
            {"block_reason": view.block_reason},
        )
    session.pending_route = route_id
    return Continuation(
        can_continue=view.can_continue,
        block_reason=view.block_reason,
        completed_play_number=view.completed_play_number,
        next_play_number=view.next_play_number,
        next_cycle_number=view.next_cycle_number,
        prompt=view.prompt,
        selected_route=route_id,
        reference=view.reference,
        routes=view.routes,
    )
