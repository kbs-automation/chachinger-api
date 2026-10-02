from tests.helpers import API, begin_play, begin_suggested_play, new_session, register, spin, submit


async def _reach_p2(client, headers):
    session = await new_session(client, headers, "strike", 555)
    p1 = await begin_suggested_play(client, headers, session)
    s = await spin(client, headers, p1["play_id"])
    assert (await submit(client, headers, p1["play_id"], s["spin_id"], "12x"))["redirect"] == (
        "next_play"
    )
    p2 = await begin_play(client, headers, session["session_id"], 4, 10, 15)
    assert p2["play_number"] == 2
    assert p2["click_cap"] == 70
    return session, p2


async def test_70_spins_without_qualifying_result_hard_exits(client):
    headers = await register(client)
    session, p2 = await _reach_p2(client, headers)

    last = None
    for i in range(1, 71):
        last = await spin(client, headers, p2["play_id"])
        assert last["at_hard_exit_cap"] is (i == 70)
        assert last["play_number"] == 2
    assert last["play_progress_pct"] == 100

    result = await submit(client, headers, p2["play_id"], last["spin_id"], "3x")
    assert result["redirect"] == "hard_exit"
    state = (await client.get(f"{API}/sessions/{session['session_id']}", headers=headers)).json()
    assert state["status"] == "hard_exit"


async def test_spin_past_p2_cap_triggers_hard_exit(client):
    headers = await register(client)
    _, p2 = await _reach_p2(client, headers)
    for _ in range(70):
        await spin(client, headers, p2["play_id"])
    over = await spin(client, headers, p2["play_id"])
    assert over["redirect"] == "hard_exit"
    assert over["at_hard_exit_cap"] is True
