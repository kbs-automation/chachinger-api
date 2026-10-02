from tests.helpers import API, begin_play, begin_suggested_play, new_session, register, spin, submit


async def test_play_and_cycle_numbers_advance_and_wrap(client):
    headers = await register(client)
    session = await new_session(client, headers, "entertainment", 1000)
    sid = session["session_id"]

    seen = []
    for i in range(8):
        if i == 0:
            play = await begin_suggested_play(client, headers, session)
        else:
            play = await begin_play(client, headers, sid, 4, 10, 15)
        s = await spin(client, headers, play["play_id"])
        assert (s["play_number"], s["cycle_number"]) == (play["play_number"], play["cycle_number"])
        result = await submit(client, headers, play["play_id"], s["spin_id"], "15x")
        assert (result["play_number"], result["cycle_number"]) == (
            play["play_number"],
            play["cycle_number"],
        )
        state = (await client.get(f"{API}/plays/{play['play_id']}", headers=headers)).json()
        assert (state["play_number"], state["cycle_number"]) == (
            play["play_number"],
            play["cycle_number"],
        )
        seen.append((play["play_number"], play["cycle_number"]))

    assert seen == [(1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1), (1, 2), (2, 2)]
    state = (await client.get(f"{API}/sessions/{sid}", headers=headers)).json()
    assert (state["play_count"], state["play_number"], state["cycle_number"]) == (8, 2, 2)


async def test_cannot_start_second_play_while_one_is_active(client):
    headers = await register(client)
    session = await new_session(client, headers)
    await begin_suggested_play(client, headers, session)
    resp = await client.post(
        f"{API}/sessions/{session['session_id']}/plays",
        json={"confirmed_base": 4, "confirmed_press": 10, "confirmed_max": 15},
        headers=headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "play_already_active"
