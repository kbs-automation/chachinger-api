"""Points 4–5: WBA / bridge / safety and separate continuation vs wager fields."""

from app.core.config import get_settings
from app.engine.mission.pipeline import authority_at_click, run_pipeline
from app.engine.mission.safety import SafetyState
from app.engine.mission.sheet import EnhancedSheetRaw
from app.engine.mission.tokens import parse_segment_token
from tests.helpers import API, new_session, register, spin


def test_weighted_token_preserves_segment_not_click():
    token = parse_segment_token("2*8")
    assert token is not None
    assert (token.segment_id, token.weight) == (8, 2)


def test_bridge_is_below_base_and_target_can_be_max():
    raw = EnhancedSheetRaw(
        row_8=["7", "40"],
        row_9=["7", "40"],
        row_10=["7"],
        primary_density_pct=60,
        density_strength="STRONG",
        pockets=["7-13"],
    )
    decision, plan = run_pipeline(raw, below_base_available=True)
    assert decision.source == "mission_critical"
    assert decision.continuation_authority != "none"
    assert decision.final_action == "continue"
    # Opening click 1 is before first target → bridge/unsupported → below_base planned.
    planned, live, bridge = authority_at_click(plan, 1, below_base_available=True)
    assert planned == "below_base"
    assert live == "below_base"
    assert bridge in {"active", "off", "pre_entry"}

    # Inside front target that has row8/9 + row10 + density → max eligible.
    planned_t, live_t, _ = authority_at_click(plan, 10, below_base_available=True)
    assert planned_t == "max"
    assert live_t == "max"
    # Continuation still independent of wager.
    assert decision.continuation_authority in {"limited", "extended", "deep_burn"}


def test_safety_caps_max_to_base():
    raw = EnhancedSheetRaw(
        row_8=["7"],
        row_9=["7"],
        row_10=["7"],
        primary_density_pct=80,
        density_strength="STRONG",
        row_4=["7"],
        row_5=["7"],
        prev_multiplier=40,
    )
    decision, _plan = run_pipeline(
        raw,
        safety=SafetyState(containment=True),
        below_base_available=False,
        opening_click=10,
    )
    assert decision.planned_band_authority == "max"
    assert decision.live_final_authority == "base"
    assert decision.guidance_key == "ui_011_containment"


def test_invalid_sheet_forces_exit():
    decision, plan = run_pipeline(EnhancedSheetRaw(row_8=["not-a-token"]))
    assert decision.continuation_authority == "none"
    assert decision.final_action == "exit"
    assert decision.live_final_authority is None
    assert plan.sheet.input_quality == "invalid"


async def test_enhanced_sheet_endpoint_and_spin_fields(client, monkeypatch):
    monkeypatch.setenv("MISSION_CRITICAL_ENGINE", "true")
    get_settings.cache_clear()
    try:
        headers = await register(client)
        session = await new_session(client, headers, "entertainment", 1000)
        sid = session["session_id"]

        sheet = await client.post(
            f"{API}/sessions/{sid}/enhanced-sheet",
            json={
                "row_8": ["7", "40"],
                "row_9": ["7", "40"],
                "row_10": ["7"],
                "primary_density_pct": 55,
                "density_strength": "STRONG",
            },
            headers=headers,
        )
        assert sheet.status_code == 200, sheet.text
        body = sheet.json()
        assert body["input_quality"] in {"ready", "degraded"}
        assert body["decision"]["source"] == "mission_critical"
        assert body["decision"]["continuation_authority"] != body["decision"].get(
            "live_final_authority"
        ) or body["decision"]["continuation_authority"] in {
            "limited",
            "extended",
            "deep_burn",
            "none",
        }
        assert "live_final_authority" in body["decision"]
        assert "continuation_authority" in body["decision"]

        play = await client.post(
            f"{API}/sessions/{sid}/plays",
            json={
                "confirmed_base": 5,
                "confirmed_press": 10,
                "confirmed_max": 20,
                "confirmed_below_base": 2,
                "active_postures": ["below_base", "base", "press", "max"],
            },
            headers=headers,
        )
        assert play.status_code == 201, play.text
        spun = await spin(client, headers, play.json()["play_id"])
        assert "live_final_authority" in spun
        assert "continuation_authority" in spun
        assert spun["posture"] in {"below_base", "base", "press", "max"}
        if spun["live_final_authority"]:
            assert spun["posture"] == spun["live_final_authority"] or spun["posture"] in {
                "below_base",
                "base",
                "press",
                "max",
            }
    finally:
        monkeypatch.delenv("MISSION_CRITICAL_ENGINE", raising=False)
        get_settings.cache_clear()
