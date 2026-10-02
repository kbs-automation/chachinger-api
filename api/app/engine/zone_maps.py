"""CONFIDENTIAL zone maps. Each zone is {"s": start_click, "e": end_click, "t": posture}.

ENTERTAINMENT_ZONES is the standard map used for Entertainment P1 and every P2+ play.
The other maps seed p1_mode_configs.zone_map; at runtime the DB copy is authoritative.
"""

from decimal import Decimal
from typing import Any

P1_UNIVERSAL_CLICK_CAP = 96
P2_PLUS_CLICK_CAP = 70
PLAYS_PER_CYCLE = 6


def _z(s: int, e: int, t: str) -> dict[str, Any]:
    return {"s": s, "e": e, "t": t}


# Original 1–64 map is LOCKED. 65–96 is the universal extension.
ENTERTAINMENT_ZONES: list[dict[str, Any]] = [
    _z(1, 6, "base"),
    _z(7, 13, "press"),
    _z(14, 16, "base"),
    _z(17, 19, "press"),
    _z(20, 33, "press"),
    _z(34, 39, "base"),
    _z(40, 42, "press"),
    _z(43, 55, "max"),
    _z(56, 59, "press"),
    _z(60, 64, "max"),
    _z(65, 79, "base"),
    _z(80, 96, "press"),
]

ENTERTAINMENT_PLUS_ZONES: list[dict[str, Any]] = [
    _z(1, 1, "max"),
    _z(2, 2, "base"),
    _z(3, 4, "max"),
    _z(5, 8, "base"),
    _z(9, 9, "max"),
    _z(10, 10, "press"),
    _z(11, 14, "max"),
    _z(15, 18, "base"),
    _z(19, 23, "max"),
    _z(24, 25, "base"),
    _z(26, 26, "max"),
    _z(27, 28, "press"),
    _z(29, 30, "max"),
    _z(31, 33, "press"),
    _z(34, 47, "base"),
    _z(48, 54, "max"),
    _z(55, 56, "base"),
    _z(57, 57, "max"),
    _z(58, 58, "base"),
    _z(59, 59, "max"),
    _z(60, 61, "base"),
    _z(62, 62, "max"),
    _z(63, 63, "base"),
    _z(64, 64, "max"),
    _z(65, 69, "base"),
    _z(70, 70, "max"),
    _z(71, 75, "base"),
    _z(76, 79, "press"),
    _z(80, 81, "max"),
    _z(82, 86, "press"),
    _z(87, 87, "max"),
    _z(88, 89, "press"),
    _z(90, 91, "max"),
    _z(92, 95, "base"),
    _z(96, 96, "max"),
]

STRIKE_ZONES: list[dict[str, Any]] = [
    _z(1, 6, "max"),
    _z(7, 13, "press"),
    _z(14, 20, "base"),
    _z(21, 29, "max"),
    _z(30, 96, "base"),
]

PURSUIT_ZONES: list[dict[str, Any]] = [
    _z(1, 6, "max"),
    _z(7, 13, "press"),
    _z(14, 20, "base"),
    _z(21, 29, "max"),
    _z(30, 43, "base"),
    _z(44, 96, "base"),
]

DEEP_RUN_PRO_ZONES: list[dict[str, Any]] = [
    _z(1, 6, "max"),
    _z(7, 13, "press"),
    _z(14, 20, "base"),
    _z(21, 29, "max"),
    _z(30, 55, "base"),
    _z(56, 64, "press"),
    _z(65, 96, "base"),
]


def _d(v: str | None) -> Decimal | None:
    return Decimal(v) if v is not None else None


MODE_SEEDS: list[dict[str, Any]] = [
    {
        "mode_id": "entertainment",
        "label": "Entertainment Mode",
        "sort_order": 1,
        "click_cap": P1_UNIVERSAL_CLICK_CAP,
        "min_budget": None,
        "baseline_base": None,
        "baseline_press": None,
        "baseline_max": None,
        "zone_map": ENTERTAINMENT_ZONES,
        "is_active": True,
    },
    {
        "mode_id": "entertainment_plus",
        "label": "Entertainment Mode+",
        "sort_order": 2,
        "click_cap": P1_UNIVERSAL_CLICK_CAP,
        "min_budget": _d("1300"),
        "baseline_base": _d("5"),
        "baseline_press": _d("10"),
        "baseline_max": _d("25"),
        "zone_map": ENTERTAINMENT_PLUS_ZONES,
        "is_active": True,
    },
    {
        "mode_id": "strike",
        "label": "Strike Mode",
        "sort_order": 3,
        "click_cap": P1_UNIVERSAL_CLICK_CAP,
        "min_budget": _d("555"),
        "baseline_base": _d("5"),
        "baseline_press": _d("10"),
        "baseline_max": _d("30"),
        "zone_map": STRIKE_ZONES,
        "is_active": True,
    },
    {
        "mode_id": "pursuit",
        "label": "Pursuit Mode",
        "sort_order": 4,
        "click_cap": P1_UNIVERSAL_CLICK_CAP,
        "min_budget": _d("625"),
        "baseline_base": _d("5"),
        "baseline_press": _d("10"),
        "baseline_max": _d("30"),
        "zone_map": PURSUIT_ZONES,
        "is_active": True,
    },
    {
        "mode_id": "deep_run_pro",
        "label": "Deep Run Pro",
        "sort_order": 5,
        "click_cap": P1_UNIVERSAL_CLICK_CAP,
        "min_budget": _d("775"),
        "baseline_base": _d("5"),
        "baseline_press": _d("10"),
        "baseline_max": _d("30"),
        "zone_map": DEEP_RUN_PRO_ZONES,
        "is_active": True,
    },
]
