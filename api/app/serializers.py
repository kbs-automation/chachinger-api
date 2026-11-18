from app.engine.zone_maps import PLAYS_PER_CYCLE
from app.models import GameSession, User
from app.schemas.auth import UserProfile
from app.schemas.routes import NextRouteResponse, RegionWagerOut, RouteCardOut, RouteReferenceOut
from app.schemas.sessions import SessionOut
from app.services import mission_decision, storage
from app.services.next_route import Continuation


def to_profile(user: User) -> UserProfile:
    return UserProfile(
        id=user.id,
        player_number=user.player_number,
        username=user.display_name,
        email=user.email,
        avatar_url=storage.avatar_url(user.avatar_url),
        tier=user.tier,
        subscription_status=user.subscription_status,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def current_play_number(session: GameSession) -> int:
    """Plays advance strictly 1..6 then wrap, so the count alone determines the position."""
    count = session.play_count or 0
    return ((count - 1) % PLAYS_PER_CYCLE) + 1 if count > 0 else 1


def to_session_out(session: GameSession) -> SessionOut:
    return SessionOut(
        id=session.id,
        p1_mode=session.p1_mode,
        status=session.status,
        session_budget=session.session_budget,
        current_balance=session.current_balance,
        total_wagered=session.total_wagered,
        confirmed_base=session.confirmed_base,
        confirmed_press=session.confirmed_press,
        confirmed_max=session.confirmed_max,
        confirmed_below_base=session.confirmed_below_base,
        play_count=session.play_count,
        play_number=current_play_number(session),
        cycle_number=session.cycle_number,
        execution_grade=session.execution_grade,
        selected_route=session.pending_route,
        started_at=session.started_at,
        ended_at=session.ended_at,
    )


def to_next_route(
    view: Continuation,
    session: GameSession | None = None,
    *,
    persist_decision: bool = True,
) -> NextRouteResponse:
    reference = view.reference
    decision = None
    if session is not None:
        decision = mission_decision.optional_out(view, session, persist=persist_decision)
    decision_id = view.decision_id
    if decision_id is None and decision is not None:
        decision_id = decision.decision_id
    return NextRouteResponse(
        can_continue=view.can_continue,
        block_reason=view.block_reason,  # type: ignore[arg-type]
        completed_play_number=view.completed_play_number,
        next_play_number=view.next_play_number,
        next_cycle_number=view.next_cycle_number,
        prompt=view.prompt,
        selected_route=view.selected_route,
        reference=None
        if reference is None
        else RouteReferenceOut(
            budget=reference.budget,
            base=reference.base,
            press=reference.press,
            max=reference.max,
            below_base=reference.below_base,
            source=reference.source,  # type: ignore[arg-type]
            ladder_status=reference.ladder_status,  # type: ignore[arg-type]
        ),
        routes=[
            RouteCardOut(
                route_id=card.route_id,
                heading=card.heading,
                detail=card.detail,
                exposure_pct=card.exposure_pct,
                risk_pct=card.risk_pct,
                end_click=card.end_click,
                start_click=card.start_click,
                pricing_scope=card.pricing_scope,  # type: ignore[arg-type]
                total_planned_wager=card.total_planned_wager,
                planned_budget_exposure_pct=card.planned_budget_exposure_pct,
                planned_balance_exposure_pct=card.planned_balance_exposure_pct,
                regions=None
                if card.regions is None
                else [RegionWagerOut.model_validate(r) for r in card.regions],
            )
            for card in view.routes
        ],
        decision=decision,
        pricing_source=view.pricing_source,  # type: ignore[arg-type]
        ladder_status=view.ladder_status,  # type: ignore[arg-type]
        decision_id=decision_id,
        engine_version=view.engine_version,
        config_version=view.config_version,
        parser_version=view.parser_version,
        offer_meta=view.offer_meta or None,
    )
