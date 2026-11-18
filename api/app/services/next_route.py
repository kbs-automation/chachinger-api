"""Pocket-route offer for the Play Complete screen.

Entertainment cards keep the static map. When the mission engine is on and a
route plan exists, Mission cards are priced from the safety-adjusted wager map.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.engine import postures, routes
from app.engine.mission.safety import SafetyState
from app.engine.mission.versions import CONFIG_VERSION, ENGINE_VERSION, PARSER_VERSION
from app.engine.mission.wager_map import cost_route, mission_endpoints, parse_mission_end_click
from app.models import GameSession
from app.services import mission_decision, play_tracker
from app.services.errors import DomainError


@dataclass(frozen=True)
class RouteCard:
    route_id: str
    heading: str
    detail: str
    exposure_pct: float
    risk_pct: float
    end_click: int | None = None
    start_click: int | None = None
    pricing_scope: str | None = None
    total_planned_wager: Decimal | None = None
    planned_budget_exposure_pct: float | None = None
    planned_balance_exposure_pct: float | None = None
    regions: tuple[dict[str, Any], ...] | None = None


@dataclass(frozen=True)
class RouteReference:
    budget: Decimal
    base: Decimal
    press: Decimal
    max: Decimal
    source: str
    below_base: Decimal | None = None
    ladder_status: str = "preliminary"


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
    pricing_source: str | None = None
    ladder_status: str | None = None
    decision_id: str | None = None
    engine_version: str | None = None
    config_version: str | None = None
    parser_version: str | None = None
    offer_meta: dict[str, Any] = field(default_factory=dict)


def _entertainment_cards(
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
        exp = routes.percent(wager, budget)
        risk = routes.percent(wager, balance)
        cards.append(
            RouteCard(
                route_id=route.route_id,
                heading=routes.heading(route),
                detail=routes.detail(route),
                exposure_pct=exp,
                risk_pct=risk,
                # Entertainment: keep click bounds off the wire (legacy contract).
                planned_budget_exposure_pct=exp,
                planned_balance_exposure_pct=risk,
                total_planned_wager=wager,
            )
        )
    return tuple(cards)


def _mission_cards(
    plan,
    *,
    start_click: int,
    budget: Decimal,
    balance: Decimal,
    base: Decimal,
    press: Decimal,
    max_bet: Decimal,
    active: tuple[str, ...],
    below_base: Decimal | None,
    safety: SafetyState | None = None,
) -> tuple[RouteCard, ...]:
    cards: list[RouteCard] = []
    for end in mission_endpoints(plan):
        if end < start_click:
            continue
        cost = cost_route(
            plan,
            end_click=end,
            start_click=start_click,
            budget=budget,
            balance=balance,
            base=base,
            press=press,
            max_bet=max_bet,
            below_base=below_base,
            active=active,
            safety=safety,
        )
        if cost is None:
            continue
        cards.append(
            RouteCard(
                route_id=cost.route_id,
                heading=f"MISSION TARGET TO CLICK {cost.end_click}",
                detail=(
                    "Authorized through this Mission endpoint."
                    if cost.pricing_scope == "full_route"
                    else "Remaining authorized cost from the next unplayed click."
                ),
                exposure_pct=cost.planned_budget_exposure_pct,
                risk_pct=cost.planned_balance_exposure_pct,
                end_click=cost.end_click,
                start_click=cost.start_click,
                pricing_scope=cost.pricing_scope,
                total_planned_wager=cost.total_planned_wager,
                planned_budget_exposure_pct=cost.planned_budget_exposure_pct,
                planned_balance_exposure_pct=cost.planned_balance_exposure_pct,
                regions=tuple(r.to_dict() for r in cost.regions),
            )
        )
    return tuple(cards)


def _persist_offer(session: GameSession, view: Continuation) -> None:
    if view.reference is None:
        return
    session.pending_quote = {
        "decision_id": view.decision_id,
        "pricing_source": view.pricing_source,
        "ladder_status": view.ladder_status,
        "budget": float(view.reference.budget),
        "base": float(view.reference.base),
        "press": float(view.reference.press),
        "max": float(view.reference.max),
        "below_base": None
        if view.reference.below_base is None
        else float(view.reference.below_base),
        "engine_version": view.engine_version,
        "config_version": view.config_version,
        "parser_version": view.parser_version,
        "routes": [
            {
                "route_id": c.route_id,
                "end_click": c.end_click,
                "total_planned_wager": None
                if c.total_planned_wager is None
                else float(c.total_planned_wager),
            }
            for c in view.routes
        ],
    }


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
    start_click: int | None = None,
    allow_during_play: bool = False,
    safety: SafetyState | None = None,
    persist_offer: bool = False,
) -> Continuation:
    """Routes the engine will accept for the next play, priced for the given ladder."""
    if session.status == "hard_exit":
        return _blocked("hard_exit")
    if session.status != "active":
        return _blocked("session_not_active")

    active_play = await play_tracker.active_play(db, session.id)
    if active_play is not None and not allow_during_play:
        return _blocked("play_in_progress")

    latest = await play_tracker.latest_play(db, session.id)
    if latest is None or latest.status not in ("completed", "manual_exit"):
        if active_play is None:
            return _blocked("no_completed_play")

    if session.current_balance <= 0:
        return _blocked("insufficient_balance")

    if active_play is not None:
        next_play, next_cycle = active_play.play_number, active_play.cycle_number
        completed = None
        default_start = max(1, (active_play.total_clicks or 0) + 1)
    else:
        assert latest is not None
        next_play, next_cycle = play_tracker.next_position(latest)
        completed = latest.play_number
        default_start = 1

    priced_budget = session.session_budget if budget is None else budget
    ladder_confirmed = base is not None and press is not None and max_bet is not None
    if not ladder_confirmed:
        base, press, max_bet = routes.reference_ladder(priced_budget)
        source = "session_budget" if budget is None else "quoted_bets"
        ladder_status = "preliminary"
    else:
        source = "quoted_bets"
        ladder_status = "confirmed"
    chosen = active or postures.chosen(None, below_base)
    if below_base is not None and below_base > base:
        raise DomainError(
            422,
            "invalid_ladder",
            "active bets must satisfy below_base ≤ base ≤ press ≤ max",
        )

    from_click = start_click or default_start
    pricing_source = "entertainment"
    decision_id = None
    mission_cards: tuple[RouteCard, ...] | None = None

    if mission_decision.enabled():
        plan = mission_decision.load_route_plan(session)
        if plan is not None and plan.targets:
            ends = mission_endpoints(plan)
            if not ends:
                return _blocked("no_qualified_mission_route")
            mission_cards = _mission_cards(
                plan,
                start_click=from_click,
                budget=priced_budget,
                balance=session.current_balance,
                base=base,
                press=press,
                max_bet=max_bet,
                active=chosen,
                below_base=below_base,
                safety=safety,
            )
            if not mission_cards:
                return _blocked("no_qualified_mission_route")
            pricing_source = "mission_critical"
            if isinstance(session.last_decision, dict):
                decision_id = session.last_decision.get("decision_id")

    cards = mission_cards or _entertainment_cards(
        priced_budget, session.current_balance, base, press, max_bet, chosen, below_base
    )

    view = Continuation(
        can_continue=active_play is None,
        block_reason="play_in_progress" if active_play is not None else None,
        completed_play_number=completed,
        next_play_number=next_play,
        next_cycle_number=next_cycle,
        prompt=None if active_play is not None else f"Choose Play-{next_play} Budget",
        selected_route=session.pending_route,
        reference=RouteReference(
            priced_budget, base, press, max_bet, source, below_base, ladder_status
        ),
        routes=cards,
        pricing_source=pricing_source,
        ladder_status=ladder_status,
        decision_id=str(decision_id) if decision_id else None,
        engine_version=ENGINE_VERSION if pricing_source == "mission_critical" else None,
        config_version=CONFIG_VERSION if pricing_source == "mission_critical" else None,
        parser_version=PARSER_VERSION if pricing_source == "mission_critical" else None,
        offer_meta={"start_click": from_click},
    )
    if persist_offer and active_play is None:
        _persist_offer(session, view)
    return view


def _blocked(reason: str) -> Continuation:
    return Continuation(False, reason, None, None, None, None, None, None, ())


async def select_route(
    db: AsyncSession,
    session: GameSession,
    route_id: str,
    *,
    decision_id: str | None = None,
) -> Continuation:
    view = await describe(db, session, persist_offer=True)
    if not view.can_continue:
        raise DomainError(
            409,
            "continuation_unavailable",
            "The next play cannot be started",
            {"block_reason": view.block_reason},
        )

    allowed = {c.route_id for c in view.routes}
    if route_id not in allowed:
        if parse_mission_end_click(route_id) is not None:
            raise DomainError(422, "route_unavailable", "That Mission route is not available")
        if routes.get_route(route_id) is None:
            raise DomainError(422, "route_unavailable", "That route is not available")
        raise DomainError(422, "route_unavailable", "That route is not available")

    if view.pricing_source == "mission_critical":
        current_id = None
        if isinstance(session.last_decision, dict):
            current_id = session.last_decision.get("decision_id")
        offered_id = view.decision_id or current_id
        if decision_id is not None and offered_id is not None and decision_id != offered_id:
            raise DomainError(
                409,
                "stale_decision",
                "Route quote is out of date; request a fresh next-route quote",
                {"expected_decision_id": offered_id, "got_decision_id": decision_id},
            )
        pending = session.pending_quote if isinstance(session.pending_quote, dict) else {}
        # If a prior quote was persisted, its decision must still match the live decision.
        if (
            pending.get("pricing_source") == "mission_critical"
            and pending.get("decision_id")
            and current_id
            and pending.get("decision_id") != current_id
        ):
            raise DomainError(
                409,
                "stale_decision",
                "Mission decision changed since the quote; request a fresh next-route quote",
                {
                    "expected_decision_id": current_id,
                    "got_decision_id": pending.get("decision_id"),
                },
            )

    session.pending_route = route_id
    _persist_offer(session, view)
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
        pricing_source=view.pricing_source,
        ladder_status=view.ladder_status,
        decision_id=view.decision_id,
        engine_version=view.engine_version,
        config_version=view.config_version,
        parser_version=view.parser_version,
        offer_meta=view.offer_meta,
    )


def require_fresh_quote_for_play(session: GameSession, *, decision_id: str | None = None) -> int:
    """Validate pending Mission quote before Begin Play. Returns click_cap."""
    route_id = session.pending_route or ""
    mission_end = parse_mission_end_click(route_id)
    if mission_end is None:
        route = routes.get_route(route_id)
        if route is None:
            raise DomainError(409, "route_required", "Choose a next-play route first")
        return route.end_click

    quote = session.pending_quote if isinstance(session.pending_quote, dict) else None
    if not quote or quote.get("pricing_source") != "mission_critical":
        raise DomainError(
            409,
            "stale_decision",
            "Mission route requires a fresh quote before Begin Play",
        )
    if decision_id is not None and quote.get("decision_id") and decision_id != quote.get("decision_id"):
        raise DomainError(
            409,
            "stale_decision",
            "Route quote is out of date; request a fresh next-route quote",
            {
                "expected_decision_id": quote.get("decision_id"),
                "got_decision_id": decision_id,
            },
        )
    if session.last_decision and isinstance(session.last_decision, dict):
        current = session.last_decision.get("decision_id")
        if current and quote.get("decision_id") and current != quote.get("decision_id"):
            raise DomainError(
                409,
                "stale_decision",
                "Mission decision changed since the quote; request a fresh next-route quote",
            )
    allowed = {r.get("route_id") for r in (quote.get("routes") or [])}
    if route_id not in allowed:
        raise DomainError(409, "route_unavailable", "Pending Mission route is not in the last quote")
    return mission_end
