"""HER / DFR / Weak Recompression protection layer (Tabs 06, 23). Protection ≠ route creation."""

from __future__ import annotations

from dataclasses import dataclass

from app.engine.mission.config_rules import (
    WR_CURRENT_MAX,
    WR_DROP_MIN,
    WR_MULT_MAX,
    WR_PREV_MIN,
)
from app.engine.mission.targets import Target


@dataclass(frozen=True)
class ProtectionState:
    weak_recompression: bool = False
    recompression_validated: bool = False
    hidden_expansion_review: bool = False
    dfr_active: bool = False
    her_active: bool = False


def weak_recompression(prev_click: int | None, current_click: int | None, mult: float | None) -> bool:
    """CFG-160 / WR-001..005 — all four conditions required."""
    if prev_click is None or current_click is None or mult is None:
        return False
    if prev_click < WR_PREV_MIN:
        return False
    if current_click > WR_CURRENT_MAX:
        return False
    if prev_click <= 0:
        return False
    drop = (prev_click - current_click) / prev_click
    if drop < WR_DROP_MIN:
        return False
    if mult >= WR_MULT_MAX:
        return False
    return True


def evaluate_protection(
    targets: list[Target],
    *,
    prev_click: int | None = None,
    current_click: int | None = None,
    current_mult: float | None = None,
) -> ProtectionState:
    wr = weak_recompression(prev_click, current_click, current_mult)
    has_front = any(t.target_type == "front" or t.end_click <= 19 for t in targets)
    has_later = any(t.start_click >= 20 for t in targets)
    dfr = has_front and has_later  # SA-062 / TC-011 — later route already qualified
    her = wr and has_later  # WR preserves hidden expansion review when farther route exists
    return ProtectionState(
        weak_recompression=wr,
        recompression_validated=False if wr else bool(
            current_mult is not None and current_mult >= WR_MULT_MAX
        ),
        hidden_expansion_review=wr,
        dfr_active=dfr,
        her_active=her or (wr and has_later),
    )
