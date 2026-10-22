from tests.helpers import API, new_session, register, spin


async def test_below_base_changes_budget_and_is_played_on_base_clicks(client):
    headers = await register(client)
    session = await new_session(client, headers, "entertainment", 1000)
    sid = session["session_id"]

    without = await client.post(
        f"{API}/sessions/{sid}/recalculate-budget",
        json={"base": 5, "press": 10, "max": 20},
        headers=headers,
    )
    with_below = await client.post(
        f"{API}/sessions/{sid}/recalculate-budget",
        json={"base": 5, "press": 10, "max": 20, "below_base": 2},
        headers=headers,
    )
    assert without.status_code == 200, without.text
    assert with_below.status_code == 200, with_below.text
    assert with_below.json()["required_budget"] < without.json()["required_budget"]

    play = await client.post(
        f"{API}/sessions/{sid}/plays",
        json={
            "confirmed_base": 5,
            "confirmed_press": 10,
            "confirmed_max": 20,
            "confirmed_below_base": 2,
        },
        headers=headers,
    )
    assert play.status_code == 201, play.text
    assert play.json()["confirmed_below_base"] == 2.0
    state = (await client.get(f"{API}/sessions/{sid}", headers=headers)).json()
    assert state["confirmed_below_base"] == 2.0

    first = await spin(client, headers, play.json()["play_id"])
    second = await spin(client, headers, play.json()["play_id"])
    third = await spin(client, headers, play.json()["play_id"])
    assert first["posture"] == "max"
    assert (second["posture"], second["next_bet_amount"]) == ("below_base", 2.0)
    assert third["posture"] == "max"

    undone = await client.post(
        f"{API}/plays/{play.json()['play_id']}/spins/undo", headers=headers
    )
    assert undone.status_code == 200, undone.text
    assert (undone.json()["posture"], undone.json()["bet_amount"]) == ("below_base", 2.0)


async def test_quote_uses_below_base_for_route_exposure(client):
    headers = await register(client)
    session = await new_session(client, headers, "entertainment", 1000)
    sid = session["session_id"]
    play = await client.post(
        f"{API}/sessions/{sid}/plays",
        json={"confirmed_base": 4, "confirmed_press": 10, "confirmed_max": 15},
        headers=headers,
    )
    spun = await spin(client, headers, play.json()["play_id"])
    done = await client.post(
        f"{API}/plays/{play.json()['play_id']}/spins/{spun['spin_id']}/result",
        json={"result": "bonus"},
        headers=headers,
    )
    assert done.status_code == 200, done.text

    plain = await client.post(
        f"{API}/sessions/{sid}/next-route/quote",
        json={"base": 5, "press": 10, "max": 20},
        headers=headers,
    )
    lowered = await client.post(
        f"{API}/sessions/{sid}/next-route/quote",
        json={"base": 5, "press": 10, "max": 20, "below_base": 1},
        headers=headers,
    )
    assert lowered.status_code == 200, lowered.text
    assert lowered.json()["reference"]["below_base"] == 1.0
    assert lowered.json()["routes"][0]["exposure_pct"] < plain.json()["routes"][0]["exposure_pct"]


async def test_below_base_must_not_exceed_base(client):
    headers = await register(client)
    session = await new_session(client, headers, "entertainment", 500)
    resp = await client.post(
        f"{API}/sessions/{session['session_id']}/recalculate-budget",
        json={"base": 5, "press": 10, "max": 20, "below_base": 8},
        headers=headers,
    )
    assert resp.status_code == 422
