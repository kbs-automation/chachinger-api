"""Map today's pocket-route continuation into the mission decision contract.

This is a transitional adapter. It does NOT implement Weighted Band Authority,
targets/bridges, or safety governors. Later phases replace this with the real
pipeline while keeping the same response field names.
"""

from __future__ import annotations

from app.engine.mission.decision import MissionDecision, build_versions, new_decision_id, utc_now_iso
from app.engine.mission.enums import (
    ContinuationAuthority,
    FinalAction,
    GuidanceKey,
    HardExitState,
    PrimaryAction,
    WagerAuthority,
)

# Pocket depth → provisional continuation label for Flutter contract testing.
_ROUTE_CONTINUATION: dict[str, tuple[ContinuationAuthority, GuidanceKey, PrimaryAction]] = {
    "early": ("limited", "ui_002_short_route", "continue"),
    "mid": ("extended", "ui_003_extended_route", "continue"),
    "deep": ("extended", "ui_003_extended_route", "continue"),
    "extreme_deep": ("deep_burn", "ui_004_deep_route", "continue_controlled"),
}


def _authority_from_ladder(*, below_base_active: bool) -> WagerAuthority:
    # Compat cannot know regional WBA yet. Prefer BELOW BASE only when the ladder
    # amount is already active; otherwise report BASE as the default controlled posture.
    return "below_base" if below_base_active else "base"


def decision_from_continuation(
    *,
    can_continue: bool,
    block_reason: str | None,
    selected_route: str | None,
    available_route_ids: list[str],
    below_base_active: bool = False,
) -> MissionDecision:
    versions = build_versions()
    calculated_at = utc_now_iso()
    decision_id = new_decision_id()

    if not can_continue:
        guidance: GuidanceKey = (
            "ui_015_manual_exit" if block_reason == "session_not_active" else "ui_010_hard_exit"
        )
        return MissionDecision(
            decision_id=decision_id,
            source="legacy_pocket_compat",
            continuation_authority="none",
            hard_exit_state="hard_exit",
            final_action="exit",
            primary_action="exit_machine",
            guidance_key=guidance,
            planned_band_authority=None,
            live_final_authority=None,
            bridge_state="off",
            exit_reason=block_reason or "no_supported_route",
            engine_version=versions.engine_version,
            config_version=versions.config_version,
            parser_version=versions.parser_version,
            calculated_at=calculated_at,
            legacy_route_id=None,
            notes=("compat: continuation blocked; full Hard Exit engine not yet active",),
        )

    route = selected_route or (available_route_ids[0] if available_route_ids else None)
    if route and route in _ROUTE_CONTINUATION:
        cont, key, action = _ROUTE_CONTINUATION[route]
    else:
        cont, key, action = ("extended", "ui_001_continue", "continue")

    authority = _authority_from_ladder(below_base_active=below_base_active)
    return MissionDecision(
        decision_id=decision_id,
        source="legacy_pocket_compat",
        continuation_authority=cont,
        hard_exit_state="normal",
        final_action="continue",
        primary_action=action,
        guidance_key=key if selected_route or route else "ui_001_continue",
        planned_band_authority=authority,
        live_final_authority=authority,
        bridge_state="off",
        exit_reason=None,
        engine_version=versions.engine_version,
        config_version=versions.config_version,
        parser_version=versions.parser_version,
        calculated_at=calculated_at,
        legacy_route_id=route,
        notes=(
            "compat: pocket route mapped to continuation labels only",
            "compat: live_final_authority is ladder default, not WBA",
        ),
    )
