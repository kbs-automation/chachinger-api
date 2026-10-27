"""Play Complete / next-play mission decision contract for Flutter (Tabs 15, 26)."""

from typing import Literal

from app.schemas.common import ResponseModel

ContinuationAuthority = Literal["none", "limited", "extended", "deep_burn"]
HardExitState = Literal["normal", "hard_exit_watch", "hard_exit_pending", "hard_exit"]
FinalAction = Literal["continue", "exit"]
PrimaryAction = Literal["continue", "continue_controlled", "exit_machine"]
WagerAuthority = Literal["below_base", "base", "press", "max"]
BridgeState = Literal["off", "active", "pre_entry"]
DecisionSource = Literal["legacy_pocket_compat", "mission_critical"]
GuidanceKey = Literal[
    "ui_001_continue",
    "ui_002_short_route",
    "ui_003_extended_route",
    "ui_004_deep_route",
    "ui_005_bridge",
    "ui_006_re_arm",
    "ui_007_exit_watch",
    "ui_008_final_route",
    "ui_009_no_qualified_route",
    "ui_010_hard_exit",
    "ui_011_containment",
    "ui_012_base_only",
    "ui_013_aggression_reduced",
    "ui_014_profit_protection",
    "ui_015_manual_exit",
]


class MissionDecisionOut(ResponseModel):
    """Conclusions-only payload. Continuation and wager authority are independent fields."""

    decision_id: str
    source: DecisionSource
    # Continuation decision (how far) — independent of wager.
    continuation_authority: ContinuationAuthority
    hard_exit_state: HardExitState
    final_action: FinalAction
    primary_action: PrimaryAction
    guidance_key: GuidanceKey
    # Wager authority (how much) — planned vs safety-adjusted final.
    planned_band_authority: WagerAuthority | None = None
    live_final_authority: WagerAuthority | None = None
    bridge_state: BridgeState = "off"
    exit_reason: str | None = None
    input_quality: Literal["ready", "degraded", "invalid"] | None = None
    engine_version: str
    config_version: str
    parser_version: str
    calculated_at: str
    legacy_route_id: str | None = None
    notes: list[str] = []
