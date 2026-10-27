"""Attach / persist mission decisions when the feature flag is on."""

from __future__ import annotations

from app.core.config import get_settings
from app.engine.mission import MissionDecision, decision_from_continuation
from app.engine.mission.pipeline import RoutePlan, authority_at_click, run_pipeline
from app.engine.mission.sheet import EnhancedSheetRaw
from app.models import GameSession
from app.schemas.decision import MissionDecisionOut
from app.services.next_route import Continuation


def enabled() -> bool:
    return get_settings().mission_critical_engine


def to_out(decision: MissionDecision) -> MissionDecisionOut:
    return MissionDecisionOut(
        decision_id=decision.decision_id,
        source=decision.source,
        continuation_authority=decision.continuation_authority,
        hard_exit_state=decision.hard_exit_state,
        final_action=decision.final_action,
        primary_action=decision.primary_action,
        guidance_key=decision.guidance_key,
        planned_band_authority=decision.planned_band_authority,
        live_final_authority=decision.live_final_authority,
        bridge_state=decision.bridge_state,
        exit_reason=decision.exit_reason,
        input_quality=decision.input_quality,  # type: ignore[arg-type]
        engine_version=decision.engine_version,
        config_version=decision.config_version,
        parser_version=decision.parser_version,
        calculated_at=decision.calculated_at,
        legacy_route_id=decision.legacy_route_id,
        notes=list(decision.notes),
    )


def _sheet_raw(session: GameSession) -> EnhancedSheetRaw | None:
    data = session.enhanced_sheet
    if not isinstance(data, dict):
        return None
    payload = data.get("raw") if isinstance(data.get("raw"), dict) else data
    if not isinstance(payload, dict):
        return None
    fields = {
        "row_2",
        "row_4",
        "row_5",
        "row_7",
        "row_8",
        "row_9",
        "row_10",
        "row_17",
        "row_18",
        "row_19",
        "primary_density_pct",
        "secondary_density_pct",
        "density_sample_n",
        "density_strength",
        "pockets",
        "source_schema_version",
        "prev_ending_click",
        "prev_multiplier",
        "prior_ending_click",
    }
    return EnhancedSheetRaw(**{k: payload.get(k) for k in fields})


def decide_from_sheet(
    session: GameSession,
    raw: EnhancedSheetRaw,
    *,
    legacy_route_id: str | None = None,
    persist: bool = True,
) -> MissionDecision:
    decision, plan = run_pipeline(
        raw,
        below_base_available=session.confirmed_below_base is not None,
        legacy_route_id=legacy_route_id,
    )
    if persist:
        session.last_decision = decision.to_dict()
        session.enhanced_sheet = plan.sheet.to_dict()
        session.route_plan = plan.to_dict()
    return decision


def from_continuation(
    view: Continuation,
    session: GameSession,
    *,
    persist: bool = True,
) -> MissionDecision | None:
    if not enabled():
        return None

    raw = _sheet_raw(session)
    if raw is not None:
        route = view.selected_route or (view.routes[0].route_id if view.routes else None)
        return decide_from_sheet(session, raw, legacy_route_id=route, persist=persist)

    decision = decision_from_continuation(
        can_continue=view.can_continue,
        block_reason=view.block_reason,
        selected_route=view.selected_route,
        available_route_ids=[card.route_id for card in view.routes],
        below_base_active=session.confirmed_below_base is not None,
    )
    if persist:
        session.last_decision = decision.to_dict()
    return decision


def optional_out(
    view: Continuation,
    session: GameSession,
    *,
    persist: bool = True,
) -> MissionDecisionOut | None:
    decision = from_continuation(view, session, persist=persist)
    return None if decision is None else to_out(decision)


def load_route_plan(session: GameSession) -> RoutePlan | None:
    if not session.route_plan:
        return None
    try:
        return RoutePlan.from_dict(session.route_plan)
    except Exception:
        return None


def spin_authority_fields(
    session: GameSession, play_click: int, posture: str
) -> dict[str, str | None]:
    """Separate continuation vs wager fields for spin responses (point 5)."""
    empty = {
        "planned_band_authority": None,
        "live_final_authority": None,
        "continuation_authority": None,
        "bridge_state": None,
    }
    if not enabled():
        return empty
    plan = load_route_plan(session)
    cont = None
    if session.last_decision and isinstance(session.last_decision, dict):
        cont = session.last_decision.get("continuation_authority")
    if plan is None or not plan.targets:
        return {
            **empty,
            "live_final_authority": posture
            if posture in {"below_base", "base", "press", "max"}
            else None,
            "continuation_authority": cont,
        }
    below = session.confirmed_below_base is not None
    planned, live, bridge = authority_at_click(
        plan, play_click, below_base_available=below
    )
    return {
        "planned_band_authority": planned,
        "live_final_authority": live,
        "continuation_authority": cont,
        "bridge_state": bridge,
    }
