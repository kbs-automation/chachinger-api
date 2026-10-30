"""Tab 11 workbook regression cases for mission-critical engine (points 4–5)."""

from app.engine.mission.continuation import evaluate_continuation
from app.engine.mission.pipeline import authority_at_click, run_pipeline
from app.engine.mission.protection import evaluate_protection, weak_recompression
from app.engine.mission.safety import SafetyState
from app.engine.mission.sheet import EnhancedSheetRaw
from app.engine.mission.targets import apply_click_progress, bridges_between, build_targets
from app.engine.mission.sheet import normalize_sheet


def _front_max_sheet(**extra) -> EnhancedSheetRaw:
    base = dict(
        row_8=["2"],
        row_9=["2"],
        row_10=["2"],
        primary_density_pct=60,
        density_strength="STRONG",
        row_4=["2"],
        row_5=["2"],
    )
    base.update(extra)
    return EnhancedSheetRaw(**base)


def test_tc010_continuation_independent_from_bridge_wager():
    raw = EnhancedSheetRaw(
        row_8=["2", "9"],
        row_9=["2", "9"],
        row_10=["2"],
        primary_density_pct=55,
        density_strength="STRONG",
        pockets=["70-80"],
    )
    decision, plan = run_pipeline(raw, below_base_available=True, opening_click=20)
    assert decision.continuation_authority in {"extended", "deep_burn"}
    planned, live, bridge = authority_at_click(plan, 25, below_base_available=True)
    assert planned == "below_base"
    assert live == "below_base"
    assert bridge == "active"
    assert decision.continuation_authority != "none"


def test_tc013_touching_targets_cluster():
    sheet = normalize_sheet(EnhancedSheetRaw(row_8=["2", "3"], row_9=["2", "3"], row_10=["2"]))
    targets = build_targets(sheet)
    assert len(targets) == 1
    assert targets[0].start_click == 7 and targets[0].end_click == 19


def test_tc014_unsupported_small_gap_stays_bridge():
    sheet = normalize_sheet(
        EnhancedSheetRaw(
            row_8=["2"],
            row_9=["2"],
            row_10=["2"],
            pockets=["17-19"],  # gap 14-16 (3 clicks), no dual gap signals
        )
    )
    targets = build_targets(sheet)
    assert len(targets) >= 2
    bridges = bridges_between(targets)
    assert bridges
    assert bridges[0].start_click == 14


def test_tc015_supported_small_gap_merges():
    sheet = normalize_sheet(
        EnhancedSheetRaw(
            row_8=["2"],
            row_9=["2"],
            row_10=["2"],
            pockets=["17-19"],
            row_19=["14-16"],
            primary_density_pct=40,
        )
    )
    targets = build_targets(sheet)
    assert len(targets) == 1
    assert targets[0].start_click == 7 and targets[0].end_click == 19


def test_tc020_max_through_terminal_click():
    decision, plan = run_pipeline(_front_max_sheet(), opening_click=13, below_base_available=True)
    planned, live, _ = authority_at_click(plan, 13, below_base_available=True)
    assert planned == "max"
    assert live == "max"
    assert decision.final_action == "continue"


def test_tc021_authority_expires_after_terminal_into_bridge():
    raw = EnhancedSheetRaw(
        row_8=["2", "6"],
        row_9=["2", "6"],
        row_10=["2"],
        primary_density_pct=55,
        density_strength="STRONG",
    )
    _decision, plan = run_pipeline(raw, below_base_available=True)
    planned, live, bridge = authority_at_click(plan, 14, below_base_available=True)
    assert planned == "below_base"
    assert live == "below_base"
    assert bridge == "active"


def test_tc022_local_max_override_with_two_corroborators():
    # Weak prior mult, but 8/9+10 + two corroborators → MAX (CFG-111).
    raw = _front_max_sheet(prev_multiplier=10, secondary_density_pct=30)
    decision, plan = run_pipeline(raw, opening_click=10)
    assert decision.planned_band_authority == "max"
    planned, _, _ = authority_at_click(plan, 10)
    assert planned == "max"


def test_tc041_row19_cannot_create_deep_alone():
    sheet = normalize_sheet(EnhancedSheetRaw(row_8=["2"], row_9=["2"], row_10=["2"], row_19=["70-80"]))
    targets = build_targets(sheet)
    assert all(t.end_click < 70 for t in targets)


def test_tc050_safety_downgrades_max_preserves_continuation():
    decision, _ = run_pipeline(
        _front_max_sheet(),
        safety=SafetyState(flip_on=True),
        opening_click=10,
    )
    assert decision.planned_band_authority == "max"
    assert decision.live_final_authority == "base"
    assert decision.continuation_authority != "none"
    assert decision.final_action == "continue"


def test_tc054_force_exit_overrides_route():
    decision, _ = run_pipeline(
        _front_max_sheet(),
        safety=SafetyState(force_exit=True),
        opening_click=10,
    )
    assert decision.final_action == "exit"
    assert decision.hard_exit_state == "hard_exit"
    assert decision.primary_action == "exit_machine"
    assert decision.live_final_authority is None


def test_tc070_deterministic_replay():
    raw = _front_max_sheet()
    d1, p1 = run_pipeline(raw, opening_click=10)
    d2, p2 = run_pipeline(raw, opening_click=10)
    assert d1.continuation_authority == d2.continuation_authority
    assert d1.planned_band_authority == d2.planned_band_authority
    assert d1.live_final_authority == d2.live_final_authority
    assert [t.to_dict() for t in p1.targets] == [t.to_dict() for t in p2.targets]


def test_tc089_weak_recompression_known_trigger():
    assert weak_recompression(118, 31, 21.0) is True
    raw = EnhancedSheetRaw(
        row_8=["2", "9"],
        row_9=["2", "9"],
        row_10=["2"],
        primary_density_pct=40,
        prior_ending_click=118,
        prev_ending_click=31,
        prev_multiplier=21,
    )
    decision, plan = run_pipeline(raw)
    assert plan.protection["weak_recompression"] is True
    assert plan.protection["hidden_expansion_review"] is True
    assert decision.continuation_authority in {"extended", "deep_burn"}


def test_tc090_wr_prior_depth_boundary():
    assert weak_recompression(59, 20, 10.0) is False


def test_tc091_wr_destination_boundary():
    assert weak_recompression(80, 40, 10.0) is False


def test_tc092_wr_strength_boundary():
    assert weak_recompression(118, 31, 25.0) is False


def test_tc093_wr_no_live_depth_does_not_invent_target():
    raw = EnhancedSheetRaw(
        row_8=["2"],
        row_9=["2"],
        row_10=["2"],
        prior_ending_click=118,
        prev_ending_click=31,
        prev_multiplier=21,
    )
    _decision, plan = run_pipeline(raw)
    assert plan.protection["weak_recompression"] is True
    assert all(t.end_click < 70 for t in plan.targets)


def test_tc096_s11_exceptional_max_all_pass():
    raw = EnhancedSheetRaw(
        row_8=["8"],
        row_9=["8"],
        row_10=["8"],
        row_19=["60-69"],
        primary_density_pct=60,
        density_strength="STRONG",
        row_4=["8"],
        prev_multiplier=30,
    )
    decision, plan = run_pipeline(raw, opening_click=65)
    assert decision.planned_band_authority == "max"
    planned, live, _ = authority_at_click(plan, 65)
    assert planned == "max"
    assert live == "max"


def test_tc097_s11_max_fails_without_second_corroborator():
    raw = EnhancedSheetRaw(
        row_8=["8"],
        row_9=["8"],
        row_10=["8"],
        primary_density_pct=60,
        density_strength="STRONG",
        prev_multiplier=30,
    )
    # Only one corroborator (density) — CFG-161 needs >=2.
    decision, _ = run_pipeline(raw, opening_click=65)
    assert decision.planned_band_authority != "max"


def test_tc098_s12_press_all_pass():
    raw = EnhancedSheetRaw(
        row_8=["9"],
        row_9=["9"],
        row_10=["9"],
        row_19=["70-80"],
        primary_density_pct=55,
        density_strength="STRONG",
        prev_multiplier=40,
    )
    decision, plan = run_pipeline(raw, opening_click=75)
    assert decision.continuation_authority == "deep_burn"
    planned, live, _ = authority_at_click(plan, 75)
    assert planned == "press"
    assert live == "press"


def test_tc099_s12_press_fails_without_extra_core():
    raw = EnhancedSheetRaw(
        row_8=["9"],
        row_9=["9"],
        primary_density_pct=55,
        density_strength="STRONG",
        prev_multiplier=40,
    )
    decision, plan = run_pipeline(raw, opening_click=75)
    planned, _, _ = authority_at_click(plan, 75)
    assert planned == "base"
    assert decision.continuation_authority in {"deep_burn", "extended", "limited"}


def test_tc100_final_target_exhaustion_hard_exit():
    raw = _front_max_sheet()
    _decision, plan = run_pipeline(raw)
    progressed = apply_click_progress(plan.targets, plan.targets[0].end_click + 1)
    cont = evaluate_continuation(progressed, input_quality="ready", current_click=plan.targets[0].end_click + 1)
    assert cont.continuation_authority == "none"
    assert cont.hard_exit_state == "hard_exit"
    assert cont.exit_reason == "final_target_exhausted"


def test_tc101_safety_downgrade_preserves_route():
    decision, _ = run_pipeline(
        _front_max_sheet(),
        safety=SafetyState(containment=True),
        opening_click=10,
    )
    assert decision.live_final_authority == "base"
    assert decision.continuation_authority != "none"
    assert decision.final_action == "continue"


def test_tc102_front_bridge_deep_handoff():
    raw = EnhancedSheetRaw(
        row_8=["2", "9"],
        row_9=["2", "9"],
        row_10=["2"],
        primary_density_pct=50,
        density_strength="STRONG",
        pockets=["70-80"],
    )
    decision, plan = run_pipeline(raw, below_base_available=True, opening_click=14)
    assert decision.continuation_authority in {"extended", "deep_burn"}
    planned, live, bridge = authority_at_click(plan, 30, below_base_available=True)
    assert planned == "below_base"
    assert live == "below_base"
    assert bridge == "active"
    deep_p, deep_l, _ = authority_at_click(plan, 75, below_base_available=True)
    assert deep_p in {"base", "press"}  # S12+ — not MAX
    assert deep_l in {"base", "press"}


def test_tc011_dfr_preserves_later_route():
    raw = EnhancedSheetRaw(
        row_8=["2", "6"],
        row_9=["2", "6"],
        row_10=["2"],
        primary_density_pct=40,
    )
    _decision, plan = run_pipeline(raw)
    assert plan.protection["dfr_active"] is True
    assert len(plan.targets) >= 2


def test_point5_fields_are_separate():
    decision, _ = run_pipeline(
        _front_max_sheet(),
        safety=SafetyState(containment=True),
        opening_click=10,
        below_base_available=True,
    )
    assert decision.planned_band_authority == "max"
    assert decision.live_final_authority == "base"
    assert decision.continuation_authority != "none"
    assert decision.primary_action in {"continue", "continue_controlled"}
    assert decision.hard_exit_state in {"normal", "hard_exit_watch", "hard_exit_pending"}
    assert decision.source == "mission_critical"
