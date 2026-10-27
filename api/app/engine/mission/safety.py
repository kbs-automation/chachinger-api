"""Safety ceiling applied after planned WBA (Tab 07). Most restrictive ceiling wins."""

from __future__ import annotations

from dataclasses import dataclass

from app.engine.mission.enums import WagerAuthority

_RANK: dict[WagerAuthority, int] = {
    "below_base": 0,
    "base": 1,
    "press": 2,
    "max": 3,
}


@dataclass(frozen=True)
class SafetyState:
    containment: bool = False
    press_suppression: bool = False
    flip_on: bool = False
    cdm: bool = False
    tws: bool = False
    pcs_unstable: bool = False
    force_exit: bool = False
    base_only: bool = False
    aggression_reduced: bool = False


def apply_safety(
    planned: WagerAuthority,
    state: SafetyState | None = None,
) -> tuple[WagerAuthority | None, str | None, bool]:
    """Return (live_final_authority, safety_reason, force_exit)."""
    state = state or SafetyState()
    if state.force_exit:
        return None, "safety_forced_exit", True

    ceiling: WagerAuthority = "max"
    reasons: list[str] = []

    if state.containment or state.base_only:
        ceiling = "base"
        reasons.append("containment" if state.containment else "base_only")
    if state.press_suppression or state.flip_on or state.cdm or state.tws or state.aggression_reduced:
        if _RANK[ceiling] > _RANK["base"]:
            ceiling = "base"
        if state.flip_on:
            reasons.append("flip_on")
        elif state.cdm:
            reasons.append("cdm")
        elif state.tws:
            reasons.append("tws")
        elif state.press_suppression:
            reasons.append("press_suppression")
        else:
            reasons.append("aggression_reduced")
    if state.pcs_unstable and _RANK[ceiling] > _RANK["press"]:
        ceiling = "press"
        reasons.append("pcs_unstable")

    reason = reasons[0] if reasons else None
    if _RANK[planned] <= _RANK[ceiling]:
        return planned, reason, False
    return ceiling, reason or "safety_ceiling", False
