"""Final safety-adjusted Mission wager map for route costing (client Mission pricing).

Builds authorized dollar amounts per click / compacted region from the stored
RoutePlan + ladder. Entertainment zone maps are not used here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.engine import postures
from app.engine.mission.pipeline import RoutePlan, authority_at_click
from app.engine.mission.safety import SafetyState
from app.engine.routes import percent

CENTS = Decimal("0.01")


@dataclass(frozen=True)
class RegionWager:
    kind: str
    start_click: int
    end_click: int
    posture: str
    amount: Decimal
    clicks: int
    subtotal: Decimal
    safety_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["amount"] = float(self.amount)
        data["subtotal"] = float(self.subtotal)
        return data


@dataclass(frozen=True)
class MissionRouteCost:
    route_id: str
    end_click: int
    start_click: int
    pricing_scope: str
    total_planned_wager: Decimal
    regions: tuple[RegionWager, ...]
    planned_budget_exposure_pct: float
    planned_balance_exposure_pct: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "end_click": self.end_click,
            "start_click": self.start_click,
            "pricing_scope": self.pricing_scope,
            "total_planned_wager": float(self.total_planned_wager),
            "regions": [r.to_dict() for r in self.regions],
            "planned_budget_exposure_pct": self.planned_budget_exposure_pct,
            "planned_balance_exposure_pct": self.planned_balance_exposure_pct,
        }


def mission_route_id(end_click: int) -> str:
    return f"mission_to_{int(end_click)}"


def parse_mission_end_click(route_id: str) -> int | None:
    if not route_id.startswith("mission_to_"):
        return None
    try:
        return int(route_id.removeprefix("mission_to_"))
    except ValueError:
        return None


def _amount_for(
    posture: str,
    *,
    kind: str,
    base: Decimal,
    press: Decimal,
    max_bet: Decimal,
    below_base: Decimal | None,
    active: tuple[str, ...],
) -> tuple[str, Decimal] | None:
    """Resolve executable dollars. Never silently raise above authorized posture.

    Bridges/pre-entry never resolve to PRESS/MAX.
    """
    enabled_bb = below_base is not None and "below_base" in active
    authorized = posture
    if kind in {"bridge", "pre_entry"} and posture in {"press", "max"}:
        authorized = "below_base" if enabled_bb else "base"
    resolved = postures.resolve(authorized, active, below_base_enabled=enabled_bb)
    order = postures.POSTURE_ORDER
    if authorized in order and resolved in order and order.index(resolved) > order.index(authorized):
        return None
    if kind in {"bridge", "pre_entry"} and resolved in {"press", "max"}:
        return None
    amounts = {
        "below_base": below_base,
        "base": base,
        "press": press,
        "max": max_bet,
    }
    amount = amounts.get(resolved)
    if amount is None:
        return None
    return resolved, amount


def build_click_authorities(
    plan: RoutePlan,
    *,
    start_click: int,
    end_click: int,
    below_base_available: bool,
    safety: SafetyState | None = None,
) -> list[tuple[int, str, str, str | None]]:
    """Return (click, kind, live_posture, safety_note) for each authorized click."""
    out: list[tuple[int, str, str, str | None]] = []
    safety = safety or SafetyState()
    for click in range(start_click, end_click + 1):
        planned, live, bridge = authority_at_click(
            plan, click, below_base_available=below_base_available, safety=safety
        )
        if bridge == "active":
            kind = "bridge"
        elif bridge == "pre_entry":
            kind = "pre_entry"
        elif planned == "below_base" or live == "below_base":
            # Unsupported / gap space planned as BELOW BASE (may sit outside formal bridges).
            kind = "bridge"
        else:
            kind = "target"
        if planned is None and live is None:
            continue
        posture = live or planned or "base"
        note = None
        if planned and live and planned != live:
            note = "safety_adjusted"
        out.append((click, kind, posture, note))
    return out


def compact_regions(
    clicks: list[tuple[int, str, str, str | None]],
    *,
    base: Decimal,
    press: Decimal,
    max_bet: Decimal,
    below_base: Decimal | None,
    active: tuple[str, ...],
) -> tuple[list[RegionWager], Decimal] | None:
    """Compact adjacent same kind/posture/amount clicks. None if a click cannot be priced."""
    if not clicks:
        return [], Decimal("0.00")
    regions: list[RegionWager] = []
    total = Decimal("0")
    run_start, run_kind, run_posture, run_note = clicks[0][0], clicks[0][1], clicks[0][2], clicks[0][3]
    run_end = run_start

    def flush(start: int, end: int, kind: str, posture: str, note: str | None) -> bool:
        nonlocal total
        priced = _amount_for(
            posture,
            kind=kind,
            base=base,
            press=press,
            max_bet=max_bet,
            below_base=below_base,
            active=active,
        )
        if priced is None:
            return False
        resolved, amount = priced
        n = end - start + 1
        sub = (amount * Decimal(n)).quantize(CENTS, rounding=ROUND_HALF_UP)
        regions.append(
            RegionWager(
                kind=kind,
                start_click=start,
                end_click=end,
                posture=resolved,
                amount=amount,
                clicks=n,
                subtotal=sub,
                safety_reason=note,
            )
        )
        total += sub
        return True

    for click, kind, posture, note in clicks[1:]:
        if kind == run_kind and posture == run_posture and note == run_note and click == run_end + 1:
            run_end = click
            continue
        if not flush(run_start, run_end, run_kind, run_posture, run_note):
            return None
        run_start, run_end, run_kind, run_posture, run_note = click, click, kind, posture, note
    if not flush(run_start, run_end, run_kind, run_posture, run_note):
        return None
    return regions, total.quantize(CENTS, rounding=ROUND_HALF_UP)


def cost_route(
    plan: RoutePlan,
    *,
    end_click: int,
    start_click: int = 1,
    budget: Decimal,
    balance: Decimal,
    base: Decimal,
    press: Decimal,
    max_bet: Decimal,
    below_base: Decimal | None,
    active: tuple[str, ...],
    safety: SafetyState | None = None,
) -> MissionRouteCost | None:
    if end_click < start_click or start_click < 1:
        return None
    below_ok = below_base is not None and "below_base" in active
    clicks = build_click_authorities(
        plan,
        start_click=start_click,
        end_click=end_click,
        below_base_available=below_ok,
        safety=safety,
    )
    compacted = compact_regions(
        clicks, base=base, press=press, max_bet=max_bet, below_base=below_base, active=active
    )
    if compacted is None:
        return None
    regions, total = compacted
    scope = "full_route" if start_click == 1 else "remaining"
    return MissionRouteCost(
        route_id=mission_route_id(end_click),
        end_click=end_click,
        start_click=start_click,
        pricing_scope=scope,
        total_planned_wager=total,
        regions=tuple(regions),
        planned_budget_exposure_pct=percent(total, budget),
        planned_balance_exposure_pct=percent(total, balance),
    )


def mission_endpoints(plan: RoutePlan) -> list[int]:
    """Qualified target ends within continuation — deepest last live target is max."""
    live = [t for t in plan.targets if t.status != "exhausted"]
    if not live:
        return []
    ends = sorted({t.end_click for t in live})
    return ends
