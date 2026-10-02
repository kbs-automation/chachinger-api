import pytest

from tests.helpers import API, begin_suggested_play, new_session, register, spin, submit

MODES = [
    ("entertainment", 1000),
    ("entertainment_plus", 1300),
    ("strike", 555),
    ("pursuit", 625),
    ("deep_run_pro", 775),
]


@pytest.mark.parametrize(("mode", "budget"), MODES)
async def test_96_spins_without_qualifying_result_hard_exits(client, mode, budget):
    headers = await register(client)
    session = await new_session(client, headers, mode, budget)
    play = await begin_suggested_play(client, headers, session)
    assert play["click_cap"] == 96

    last = None
    for i in range(1, 97):
        last = await spin(client, headers, play["play_id"])
        assert last["redirect"] == "continue"
        assert last["at_hard_exit_cap"] is (i == 96)
    assert last["play_progress_pct"] == 100

    result = await submit(client, headers, play["play_id"], last["spin_id"], "2x")
    assert result["qualifying"] is False
    assert result["redirect"] == "hard_exit"

    state = (await client.get(f"{API}/sessions/{session['session_id']}", headers=headers)).json()
    assert state["status"] == "hard_exit"
    assert state["execution_grade"] == "A+"


async def test_spin_past_p1_cap_triggers_hard_exit(client):
    headers = await register(client)
    session = await new_session(client, headers, "entertainment", 1000)
    play = await begin_suggested_play(client, headers, session)
    for _ in range(96):
        await spin(client, headers, play["play_id"])

    over = await spin(client, headers, play["play_id"])
    assert over["redirect"] == "hard_exit"
    assert over["at_hard_exit_cap"] is True
    assert over["spin_id"] is None

    state = (await client.get(f"{API}/plays/{play['play_id']}", headers=headers)).json()
    assert state["status"] == "hard_exit"
    again = await client.post(f"{API}/plays/{play['play_id']}/spins", headers=headers)
    assert again.status_code == 409
