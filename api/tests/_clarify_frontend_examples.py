"""Print real JSON for frontend clarification — run: pytest -s tests/_clarify_frontend_examples.py"""

import json

import pytest

from app.core.config import get_settings
from app.engine.mission.pipeline import authority_at_click, run_pipeline
from app.engine.mission.sheet import EnhancedSheetRaw
from app.engine.mission.tokens import parse_segment_list
from tests.helpers import API, new_session, register, spin


_OUT: list[str] = []


def _dump(label: str, obj: dict) -> None:
    block = f"\n==== {label} ====\n{json.dumps(obj, indent=2, default=str)}"
    _OUT.append(block)
    print(block.encode("ascii", "replace").decode("ascii"))


@pytest.fixture
def mission_on(monkeypatch):
    monkeypatch.setenv("MISSION_CRITICAL_ENGINE", "true")
    get_settings.cache_clear()
    yield
    monkeypatch.delenv("MISSION_CRITICAL_ENGINE", raising=False)
    get_settings.cache_clear()


async def test_1_below_base_live_without_active_posture(client, mission_on):
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
    _dump("1 enhanced-sheet decision (bridge -> below_base planned/live)", sheet.json())

    # a/c: amount present but below_base NOT in active_postures (app never sends it)
    play = await client.post(
        f"{API}/sessions/{sid}/plays",
        json={
            "confirmed_base": 5,
            "confirmed_press": 10,
            "confirmed_max": 20,
            "confirmed_below_base": 2,
            "active_postures": ["base", "press", "max"],
        },
        headers=headers,
    )
    assert play.status_code == 201, play.text
    _dump("1a start-play (below_base amount set, NOT in active_postures)", play.json())

    spun = await spin(client, headers, play.json()["play_id"])
    _dump("1a first spin", spun)

    # b: omit confirmed_below_base entirely
    # need new session play path — discard and use new session
    headers2 = await register(client)
    session2 = await new_session(client, headers2, "entertainment", 1000)
    sid2 = session2["session_id"]
    await client.post(
        f"{API}/sessions/{sid2}/enhanced-sheet",
        json={
            "row_8": ["7", "40"],
            "row_9": ["7", "40"],
            "row_10": ["7"],
            "primary_density_pct": 55,
            "density_strength": "STRONG",
        },
        headers=headers2,
    )
    play2 = await client.post(
        f"{API}/sessions/{sid2}/plays",
        json={
            "confirmed_base": 5,
            "confirmed_press": 10,
            "confirmed_max": 20,
            "active_postures": ["base", "press", "max"],
        },
        headers=headers2,
    )
    assert play2.status_code == 201, play2.text
    _dump("1b start-play (confirmed_below_base omitted)", play2.json())
    spun2 = await spin(client, headers2, play2.json()["play_id"])
    _dump("1b first spin", spun2)


async def test_2_bridge_target_expiry_sequence(client, mission_on):
    headers = await register(client)
    session = await new_session(client, headers, "entertainment", 2000)
    sid = session["session_id"]
    await client.post(
        f"{API}/sessions/{sid}/enhanced-sheet",
        json={
            "row_8": ["7", "40"],
            "row_9": ["7", "40"],
            "row_10": ["7"],
            "primary_density_pct": 60,
            "density_strength": "STRONG",
            "row_4": ["7"],
            "row_5": ["7"],
            "prev_multiplier": 40,
        },
        headers=headers,
    )
    play = await client.post(
        f"{API}/sessions/{sid}/plays",
        json={"confirmed_base": 5, "confirmed_press": 10, "confirmed_max": 20},
        headers=headers,
    )
    assert play.status_code == 201, play.text
    pid = play.json()["play_id"]

    # Unit-level authority across clicks for the stored plan shape
    raw = EnhancedSheetRaw(
        row_8=["7", "40"],
        row_9=["7", "40"],
        row_10=["7"],
        primary_density_pct=60,
        density_strength="STRONG",
        row_4=["7"],
        row_5=["7"],
        prev_multiplier=40,
    )
    _decision, plan = run_pipeline(raw, below_base_available=False)
    seq = []
    for click in [1, 5, 7, 10, 13, 14, 20]:
        planned, live, bridge = authority_at_click(plan, click, below_base_available=False)
        seq.append(
            {
                "click": click,
                "planned_band_authority": planned,
                "live_final_authority": live,
                "bridge_state": bridge,
            }
        )
    _dump("2c authority_at_click sequence (bridge->target->after expiry)", {"sequence": seq})
    from pathlib import Path

    Path("tests/_clarify_out.json.txt").write_text("\n".join(_OUT), encoding="utf-8")

    # Real spin #1 from API
    spun = await spin(client, headers, pid)
    _dump("2c first live spin response", spun)


def test_3_real_lookup_tokens():
    rows = {
        "row_4": ["1*138", "2*95", "3*74", "4*64"],
        "row_8": ["1*6", "4*7", "2*7", "11", "25", "3*3"],
        "row_10": ["2*7", "4*7"],
    }
    out = {k: [{"raw": t.raw, "segment_id": t.segment_id, "weight": t.weight} for t in parse_segment_list(v)] for k, v in rows.items()}
    _dump("3 server parse (segment-first Lookup)", out)
