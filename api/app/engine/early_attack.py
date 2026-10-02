"""CONFIDENTIAL. Early Attack authorization — stub, awaiting spec.

Mirrors the signal shape used by the mobile app so the real rules can be dropped in.
Until the spec lands, authorize() always returns False and the engine never emits
the early_attack posture.
"""

from dataclasses import dataclass
from decimal import Decimal

MIN_CLICK = 7
MAX_CLICK = 13
SIZE_FACTOR = Decimal("1.20")


@dataclass(frozen=True)
class EarlyAttackSignals:
    current_click: int
    prev_play_reached_25x_or_greater: bool = False
    prev_play_band_b_or_c_ignition: bool = False
    two_of_last_three_reached_before_click_20: bool = False
    flip_on: bool = False
    cdm: bool = False
    hard_containment: bool = False
    hard_exit_watch: bool = False
    press_suppression_lock: bool = False
    confirmed_dead_session: bool = False


def in_window(click: int) -> bool:
    return MIN_CLICK <= click <= MAX_CLICK


def authorize(signals: EarlyAttackSignals) -> bool:
    return False
