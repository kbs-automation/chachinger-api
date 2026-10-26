"""Mission decision contract — flag off must not change existing payloads."""

from app.core.config import get_settings
from app.engine.mission.compat import decision_from_continuation
from tests.helpers import API, new_session, register, spin


def test_compat_maps_hard_exit_and_pocket_routes():
    blocked = decision_from_continuation(
        can_continue=False,
        block_reason="hard_exit",
        selected_route=None,
        available_route_ids=[],
    )
    assert blocked.continuation_authority == "none"
    assert blocked.hard_exit_state == "hard_exit"
    assert blocked.primary_action == "exit_machine"
    assert blocked.guidance_key == "ui_010_hard_exit"
    assert blocked.source == "legacy_pocket_compat"

    early = decision_from_continuation(
        can_continue=True,
        block_reason=None,
        selected_route="early",
        available_route_ids=["early", "mid", "deep", "extreme_deep"],
    )
    assert early.continuation_authority == "limited"
    assert early.guidance_key == "ui_002_short_route"
    assert early.legacy_route_id == "early"

    deep = decision_from_continuation(
        can_continue=True,
        block_reason=None,
        selected_route="extreme_deep",
        available_route_ids=["extreme_deep"],
        below_base_active=True,
    )
    assert deep.continuation_authority == "deep_burn"
    assert deep.primary_action == "continue_controlled"
    assert deep.live_final_authority == "below_base"


async def test_flag_off_omits_decision(client):
    assert get_settings().mission_critical_engine is False
    headers = await register(client)
    session = await new_session(client, headers, "entertainment", 1000)
    sid = session["session_id"]
    play = await client.post(
        f"{API}/sessions/{sid}/plays",
        json={"confirmed_base": 5, "confirmed_press": 10, "confirmed_max": 20},
        headers=headers,
    )
    spun = await spin(client, headers, play.json()["play_id"])
    done = await client.post(
        f"{API}/plays/{play.json()['play_id']}/spins/{spun['spin_id']}/result",
        json={"result": "bonus"},
        headers=headers,
    )
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["decision"] is None
    assert body["continuation"]["decision"] is None


async def test_flag_on_attaches_decision(client, monkeypatch):
    monkeypatch.setenv("MISSION_CRITICAL_ENGINE", "true")
    get_settings.cache_clear()
    try:
        assert get_settings().mission_critical_engine is True
        headers = await register(client)
        session = await new_session(client, headers, "entertainment", 1000)
        sid = session["session_id"]
        play = await client.post(
            f"{API}/sessions/{sid}/plays",
            json={"confirmed_base": 5, "confirmed_press": 10, "confirmed_max": 20},
            headers=headers,
        )
        spun = await spin(client, headers, play.json()["play_id"])
        done = await client.post(
            f"{API}/plays/{play.json()['play_id']}/spins/{spun['spin_id']}/result",
            json={"result": "bonus"},
            headers=headers,
        )
        assert done.status_code == 200, done.text
        body = done.json()
        decision = body["decision"]
        assert decision is not None
        assert body["continuation"]["decision"]["decision_id"] == decision["decision_id"]
        assert decision["source"] == "legacy_pocket_compat"
        assert decision["final_action"] == "continue"
        assert decision["primary_action"] in ("continue", "continue_controlled")
        assert decision["guidance_key"].startswith("ui_")
        assert decision["engine_version"]
        assert decision["legacy_route_id"] in ("early", "mid", "deep", "extreme_deep")

        chosen = await client.post(
            f"{API}/sessions/{sid}/next-route",
            json={"route_id": "early"},
            headers=headers,
        )
        assert chosen.status_code == 200, chosen.text
        assert chosen.json()["decision"]["legacy_route_id"] == "early"
        assert chosen.json()["decision"]["continuation_authority"] == "limited"
    finally:
        monkeypatch.delenv("MISSION_CRITICAL_ENGINE", raising=False)
        get_settings.cache_clear()
