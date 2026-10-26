"""Attach / persist mission decisions when the feature flag is on."""

from __future__ import annotations

from app.core.config import get_settings
from app.engine.mission import MissionDecision, decision_from_continuation
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
        engine_version=decision.engine_version,
        config_version=decision.config_version,
        parser_version=decision.parser_version,
        calculated_at=decision.calculated_at,
        legacy_route_id=decision.legacy_route_id,
        notes=list(decision.notes),
    )


def from_continuation(
    view: Continuation,
    session: GameSession,
    *,
    persist: bool = True,
) -> MissionDecision | None:
    if not enabled():
        return None
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
