"""Next-play pocket routes. Depth boundaries stay in this module and are never serialized.

A route includes every shallower pocket and stops at its own depth. Play-2 and later
use the standard map; these depths are cut on zone boundaries inside that map.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.engine import mode_engine, postures, zone_maps

CENTS = Decimal("0.01")
TENTH = Decimal("0.1")


@dataclass(frozen=True)
class RouteDef:
    route_id: str
    pockets: int
    end_click: int


# Cumulative stops on the standard next-play map. Not part of any API response.
ROUTES: tuple[RouteDef, ...] = (
    RouteDef("early", 1, 18),
    RouteDef("mid", 2, 33),
    RouteDef("deep", 3, 54),
    RouteDef("extreme_deep", 4, zone_maps.P2_PLUS_CLICK_CAP),
)
_BY_ID = {route.route_id: route for route in ROUTES}


def get_route(route_id: str) -> RouteDef | None:
    return _BY_ID.get(route_id)


def heading(route: RouteDef) -> str:
    name = {
        "early": "EARLY",
        "mid": "MID",
        "deep": "DEEP",
        "extreme_deep": "EXTREME DEEP",
    }[route.route_id]
    word = "POCKET" if route.pockets == 1 else "POCKETS"
    return f"{name} {word} DETECTED"


def detail(route: RouteDef) -> str:
    if route.pockets == 1:
        return "Continue through the early pocket only on the next play."
    if route.route_id == "extreme_deep":
        return "Continue through extreme deep pockets on the next play."
    phrase = {"mid": "mid pockets", "deep": "deep pockets"}[route.route_id]
    return f"Continue through {phrase} only on the next play."


def reference_ladder(budget: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """Cent-rounded Risk Unit ladder (0.40 / 1.00 / 1.40), matching the app's next-play bets."""
    ru = budget / Decimal(100) if budget > 0 else Decimal(0)

    def money(factor: str) -> Decimal:
        return (ru * Decimal(factor)).quantize(CENTS, rounding=ROUND_HALF_UP)

    return money("0.40"), money("1.00"), money("1.40")


def _through(end_click: int) -> list[dict[str, Any]]:
    sliced: list[dict[str, Any]] = []
    for zone in zone_maps.ENTERTAINMENT_ZONES:
        start, end = int(zone["s"]), int(zone["e"])
        if start > end_click:
            break
        sliced.append({**zone, "e": min(end, end_click)})
    return sliced


def route_wager(
    route_id: str,
    base: Decimal,
    press: Decimal,
    max_bet: Decimal,
    active: tuple[str, ...] = postures.DEFAULT_ACTIVE,
    below_base: Decimal | None = None,
) -> Decimal:
    route = _BY_ID[route_id]
    return mode_engine.zone_exposure(
        _through(route.end_click),
        base,
        press,
        max_bet,
        below_base=below_base,
        active=active,
    )


def percent(part: Decimal, whole: Decimal) -> float:
    if whole <= 0:
        return 0.0
    return float((part / whole * Decimal(100)).quantize(TENTH, rounding=ROUND_HALF_UP))
