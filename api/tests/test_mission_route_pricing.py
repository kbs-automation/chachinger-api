"""Mission-priced next-route cards (bridge/BELOW BASE + safety downgrade)."""

from decimal import Decimal

from app.engine.mission.pipeline import run_pipeline
from app.engine.mission.safety import SafetyState
from app.engine.mission.sheet import EnhancedSheetRaw
from app.engine.mission.wager_map import cost_route, mission_endpoints, mission_route_id


def _sheet_front_and_later() -> EnhancedSheetRaw:
    return EnhancedSheetRaw(
        row_8=["2", "6"],
        row_9=["2", "6"],
        row_10=["2"],
        primary_density_pct=60,
        density_strength="STRONG",
        row_4=["2"],
        row_5=["2"],
        token_format="segment_count_v1",
    )


def test_mission_bridge_below_base_cost():
    decision, plan = run_pipeline(_sheet_front_and_later(), below_base_available=True)
    assert decision.final_action == "continue"
    ends = mission_endpoints(plan)
    assert ends
    front_end = ends[0]
    cost = cost_route(
        plan,
        end_click=front_end,
        start_click=1,
        budget=Decimal("1000"),
        balance=Decimal("1000"),
        base=Decimal("5"),
        press=Decimal("10"),
        max_bet=Decimal("20"),
        below_base=Decimal("2"),
        active=("below_base", "base", "press", "max"),
    )
    assert cost is not None
    assert cost.route_id == mission_route_id(front_end)
    assert cost.regions
    bridge = cost.regions[0]
    assert bridge.kind in {"bridge", "pre_entry", "target"}
    # Opening unsupported region prices at BELOW BASE when available.
    kinds = {r.kind for r in cost.regions}
    postures = {r.posture for r in cost.regions}
    assert cost.total_planned_wager > 0
    assert cost.planned_budget_exposure_pct == cost.planned_balance_exposure_pct
    assert "below_base" in postures or "base" in postures
    assert cost.pricing_scope == "full_route"
    # No PRESS/MAX on bridge regions.
    for region in cost.regions:
        if region.kind in {"bridge", "pre_entry"}:
            assert region.posture in {"below_base", "base"}


def test_mission_safety_downgrade_reduces_total():
    _, plan = run_pipeline(_sheet_front_and_later(), below_base_available=True)
    end = mission_endpoints(plan)[0]
    plain = cost_route(
        plan,
        end_click=end,
        budget=Decimal("1000"),
        balance=Decimal("1000"),
        base=Decimal("5"),
        press=Decimal("10"),
        max_bet=Decimal("20"),
        below_base=Decimal("2"),
        active=("below_base", "base", "press", "max"),
    )
    capped = cost_route(
        plan,
        end_click=end,
        budget=Decimal("1000"),
        balance=Decimal("1000"),
        base=Decimal("5"),
        press=Decimal("10"),
        max_bet=Decimal("20"),
        below_base=Decimal("2"),
        active=("below_base", "base", "press", "max"),
        safety=SafetyState(containment=True),
    )
    assert plain is not None and capped is not None
    assert capped.total_planned_wager <= plain.total_planned_wager
    assert all(r.posture in {"below_base", "base"} for r in capped.regions)


def test_remaining_scope_from_mid_route():
    _, plan = run_pipeline(_sheet_front_and_later(), below_base_available=True)
    end = mission_endpoints(plan)[0]
    full = cost_route(
        plan,
        end_click=end,
        start_click=1,
        budget=Decimal("1000"),
        balance=Decimal("800"),
        base=Decimal("5"),
        press=Decimal("10"),
        max_bet=Decimal("20"),
        below_base=Decimal("2"),
        active=("below_base", "base", "press", "max"),
    )
    rem = cost_route(
        plan,
        end_click=end,
        start_click=8,
        budget=Decimal("1000"),
        balance=Decimal("800"),
        base=Decimal("5"),
        press=Decimal("10"),
        max_bet=Decimal("20"),
        below_base=Decimal("2"),
        active=("below_base", "base", "press", "max"),
    )
    assert full is not None and rem is not None
    assert rem.pricing_scope == "remaining"
    assert rem.total_planned_wager < full.total_planned_wager
    assert rem.start_click == 8
