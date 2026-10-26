"""Locked enums for the mission-critical decision payload (Tabs 01, 10, 15, 26)."""

from typing import Literal

ContinuationAuthority = Literal["none", "limited", "extended", "deep_burn"]
HardExitState = Literal["normal", "hard_exit_watch", "hard_exit_pending", "hard_exit"]
FinalAction = Literal["continue", "exit"]
PrimaryAction = Literal["continue", "continue_controlled", "exit_machine"]
WagerAuthority = Literal["below_base", "base", "press", "max"]
BridgeState = Literal["off", "active", "pre_entry"]
DecisionSource = Literal["legacy_pocket_compat", "mission_critical"]

# Tab 26 UI IDs — Flutter maps these to locked copy; engine never invents free text.
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
