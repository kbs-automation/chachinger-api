"""Continuation authority + Hard Exit state machine (Tabs 01, 03)."""

from __future__ import annotations

from dataclasses import dataclass

from app.engine.mission.enums import (
    ContinuationAuthority,
    FinalAction,
    GuidanceKey,
    HardExitState,
    PrimaryAction,
)
from app.engine.mission.protection import ProtectionState
from app.engine.mission.targets import Target, live_targets


@dataclass(frozen=True)
class ContinuationResult:
    continuation_authority: ContinuationAuthority
    hard_exit_state: HardExitState
    final_action: FinalAction
    primary_action: PrimaryAction
    guidance_key: GuidanceKey
    exit_reason: str | None
    last_target_end: int | None


def evaluate_continuation(
    targets: list[Target],
    *,
    input_quality: str,
    force_exit: bool = False,
    protection: ProtectionState | None = None,
    current_click: int | None = None,
) -> ContinuationResult:
    if force_exit:
        return ContinuationResult(
            continuation_authority="none",
            hard_exit_state="hard_exit",
            final_action="exit",
            primary_action="exit_machine",
            guidance_key="ui_010_hard_exit",
            exit_reason="safety_forced_exit",
            last_target_end=None,
        )

    alive = live_targets(targets)
    protection = protection or ProtectionState()

    # TC-012 / TC-100 — no live targets and no protection → HARD EXIT.
    if input_quality == "invalid" or (not alive and not (protection.her_active or protection.dfr_active)):
        if not alive:
            return ContinuationResult(
                continuation_authority="none",
                hard_exit_state="hard_exit",
                final_action="exit",
                primary_action="exit_machine",
                guidance_key="ui_009_no_qualified_route",
                exit_reason="final_target_exhausted" if targets else "no_supported_route",
                last_target_end=max((t.end_click for t in targets), default=None),
            )

    if not alive:
        return ContinuationResult(
            continuation_authority="none",
            hard_exit_state="hard_exit",
            final_action="exit",
            primary_action="exit_machine",
            guidance_key="ui_010_hard_exit",
            exit_reason="final_target_exhausted",
            last_target_end=max((t.end_click for t in targets), default=None),
        )

    last_end = max(t.end_click for t in alive)
    has_deep = any(t.target_type in {"deep", "isolated"} or t.end_click >= 70 for t in alive)
    has_extended = any(t.end_click >= 33 for t in alive)

    if has_deep:
        cont: ContinuationAuthority = "deep_burn"
        guidance: GuidanceKey = "ui_004_deep_route"
        primary: PrimaryAction = "continue_controlled"
    elif has_extended or protection.dfr_active or protection.her_active:
        cont = "extended"
        guidance = "ui_003_extended_route"
        primary = "continue"
    else:
        cont = "limited"
        guidance = "ui_002_short_route"
        primary = "continue"

    # Hard Exit state machine (HE-050..096).
    if len(alive) > 1:
        hard: HardExitState = "normal"
    elif current_click is not None and alive[0].start_click <= current_click <= alive[0].end_click:
        # Final target active/imminent → PENDING (HE-053 / UI-008).
        hard = "hard_exit_pending"
        guidance = "ui_008_final_route"
        primary = "continue_controlled"
    elif len(alive) == 1:
        hard = "hard_exit_watch"
        guidance = "ui_007_exit_watch"
        primary = "continue_controlled"
    else:
        hard = "normal"

    return ContinuationResult(
        continuation_authority=cont,
        hard_exit_state=hard,
        final_action="continue",
        primary_action=primary,
        guidance_key=guidance,
        exit_reason=None,
        last_target_end=last_end,
    )
