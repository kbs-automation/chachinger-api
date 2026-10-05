"""Behaviour the mobile app relies on: posture selection, bets entered by hand, dollar
win entry, undoing a spin and discarding a session abandoned during bet setup."""

from tests.helpers import (
    API,
    begin_play,
    begin_suggested_play,
    keys_matching,
    new_session,
    register,
    spin,
)

# Strike's 96-click map holds 15 MAX, 7 PRESS and 74 BASE clicks.


async def _recalc(client, headers, sid, base, press, max_bet, active=None):
    body = {"base": base, "press": press, "max": max_bet}
    if active is not None:
        body["active_postures"] = active
    resp = await client.post(f"{API}/sessions/{sid}/recalculate-budget", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_switched_off_posture_reprices_budget_and_plays_nearest_posture(client):
    headers = await register(client)
    session = await new_session(client, headers, "strike", 555)
    sid = session["session_id"]

    # PRESS off: its 7 clicks are played at BASE. 15×$30 + 81×$5 = $855.
    assert (await _recalc(client, headers, sid, 5, 10, 30, ["base", "max"]))["new_budget"] == 855
    # BASE off: its clicks move up to PRESS. 15×$30 + 81×$10 = $1,260.
    assert (await _recalc(client, headers, sid, 5, 10, 30, ["press", "max"]))["new_budget"] == 1260
    # MAX off: its clicks drop to PRESS. 22×$10 + 74×$5 = $590.
    assert (await _recalc(client, headers, sid, 5, 10, 30, ["base", "press"]))["new_budget"] == 590
    # Every posture back on returns to the published minimum ladder.
    assert (await _recalc(client, headers, sid, 5, 10, 30))["new_budget"] == 890

    await _recalc(client, headers, sid, 5, 10, 30, ["base", "max"])
    resp = await client.post(
        f"{API}/sessions/{sid}/plays",
        json={
            "confirmed_base": 5,
            "confirmed_press": 10,
            "confirmed_max": 30,
            "active_postures": ["base", "max"],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    play_id = resp.json()["play_id"]

    spins = [await spin(client, headers, play_id) for _ in range(7)]
    assert [s["posture"] for s in spins[:6]] == ["max"] * 6
    assert (spins[6]["posture"], spins[6]["next_bet_amount"]) == ("base", 5.0)


async def test_postures_need_two_active_and_ignore_switched_off_amounts(client):
    headers = await register(client)
    session = await new_session(client, headers, "strike", 555)
    sid = session["session_id"]

    one = await client.post(
        f"{API}/sessions/{sid}/recalculate-budget",
        json={"base": 5, "press": 10, "max": 30, "active_postures": ["max"]},
        headers=headers,
    )
    assert one.status_code == 422

    # PRESS is off, so its out-of-order amount does not matter.
    body = await _recalc(client, headers, sid, 5, 50, 30, ["base", "max"])
    assert body["new_budget"] == 855


async def test_bets_entered_by_hand_may_sit_below_the_mode_baseline(client):
    headers = await register(client)
    session = await new_session(client, headers, "strike", 555)
    sid = session["session_id"]

    # 15×$18 + 7×$6 + 74×$3 = $534: hand-entered bets cost exactly their exposure.
    body = await _recalc(client, headers, sid, 3, 6, 18)
    assert body["new_budget"] == 534
    assert body["current_balance"] == 534

    play = await begin_play(client, headers, sid, 3, 6, 18)
    assert play["session_budget"] == 534
    first = await spin(client, headers, play["play_id"])
    assert (first["posture"], first["next_bet_amount"]) == ("max", 18.0)


async def test_win_entered_in_dollars_becomes_a_multiplier_of_the_bet(client):
    headers = await register(client)
    session = await new_session(client, headers, "strike", 555)
    play = await begin_suggested_play(client, headers, session)
    pid = play["play_id"]

    small = await spin(client, headers, pid)
    resp = await client.post(
        f"{API}/plays/{pid}/spins/{small['spin_id']}/result",
        json={"win_amount": 60},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["multiplier"] == 2.0
    assert resp.json()["qualifying"] is False
    assert resp.json()["redirect"] == "continue"
    assert resp.json()["current_balance"] == 890 - 30 + 60

    big = await spin(client, headers, pid)
    resp = await client.post(
        f"{API}/plays/{pid}/spins/{big['spin_id']}/result",
        json={"win_amount": 450},
        headers=headers,
    )
    body = resp.json()
    assert (body["multiplier"], body["qualifying"], body["redirect"]) == (15.0, True, "next_play")
    assert body["win_amount"] == 450.0
    assert body["current_balance"] == 920 - 30 + 450


async def test_bonus_takes_a_dollar_payout_and_multiplier_rejects_one(client):
    headers = await register(client)
    session = await new_session(client, headers, "strike", 555)
    play = await begin_suggested_play(client, headers, session)
    pid = play["play_id"]
    s = await spin(client, headers, pid)
    url = f"{API}/plays/{pid}/spins/{s['spin_id']}/result"

    assert (await client.post(url, json={}, headers=headers)).status_code == 422
    mixed = await client.post(url, json={"result": "34x", "win_amount": 10}, headers=headers)
    assert mixed.status_code == 422

    bonus = await client.post(url, json={"result": "bonus", "win_amount": 200}, headers=headers)
    assert bonus.status_code == 200, bonus.text
    assert bonus.json()["qualifying"] is True
    assert bonus.json()["multiplier"] is None
    assert bonus.json()["win_amount"] == 200.0


async def test_undo_reverses_the_latest_spin(client):
    headers = await register(client)
    session = await new_session(client, headers, "strike", 555)
    play = await begin_suggested_play(client, headers, session)
    pid = play["play_id"]
    undo_url = f"{API}/plays/{pid}/spins/undo"

    await spin(client, headers, pid)
    second = await spin(client, headers, pid)
    assert second["current_balance"] == 830.0

    undone = await client.post(undo_url, headers=headers)
    assert undone.status_code == 200, undone.text
    body = undone.json()
    assert body["current_balance"] == 860.0
    assert (body["posture"], body["bet_amount"], body["has_spins"]) == ("max", 30.0, True)
    assert body["play_number"] == 1 and body["cycle_number"] == 1
    assert keys_matching(body, "click") == []

    body = (await client.post(undo_url, headers=headers)).json()
    assert body["has_spins"] is False
    assert body["current_balance"] == 890.0
    assert body["play_progress_pct"] == 0

    empty = await client.post(undo_url, headers=headers)
    assert empty.status_code == 409
    assert empty.json()["detail"]["code"] == "nothing_to_undo"

    state = (await client.get(f"{API}/sessions/{session['session_id']}", headers=headers)).json()
    assert state["total_wagered"] == 0.0

    again = await spin(client, headers, pid)
    assert again["current_balance"] == 860.0
    await client.post(
        f"{API}/plays/{pid}/spins/{again['spin_id']}/result",
        json={"result": "2x"},
        headers=headers,
    )
    locked = await client.post(undo_url, headers=headers)
    assert locked.status_code == 409
    assert locked.json()["detail"]["code"] == "result_already_submitted"


async def test_unplayed_session_can_be_discarded_but_played_one_cannot(client):
    headers = await register(client)
    session = await new_session(client, headers, "strike", 555)
    sid = session["session_id"]

    assert (await client.delete(f"{API}/sessions/{sid}", headers=headers)).status_code == 204
    assert (await client.get(f"{API}/sessions/{sid}", headers=headers)).status_code == 404

    played = await new_session(client, headers, "entertainment", 1000)
    await begin_suggested_play(client, headers, played)
    resp = await client.delete(f"{API}/sessions/{played['session_id']}", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "session_has_plays"


async def test_play_without_spins_can_be_discarded_and_restarted_as_play_one(client):
    headers = await register(client)
    session = await new_session(client, headers, "strike", 555)
    sid = session["session_id"]
    first = await begin_suggested_play(client, headers, session)

    resp = await client.delete(f"{API}/plays/{first['play_id']}", headers=headers)
    assert resp.status_code == 204
    state = (await client.get(f"{API}/sessions/{sid}", headers=headers)).json()
    assert state["play_count"] == 0

    await _recalc(client, headers, sid, 10, 20, 60)
    again = await begin_play(client, headers, sid, 10, 20, 60)
    assert (again["play_number"], again["click_cap"]) == (1, 96)

    await spin(client, headers, again["play_id"])
    spun = await client.delete(f"{API}/plays/{again['play_id']}", headers=headers)
    assert spun.status_code == 409
    assert spun.json()["detail"]["code"] == "play_has_spins"


async def test_suggest_matches_what_a_new_session_would_offer(client):
    headers = await register(client)
    resp = await client.post(
        f"{API}/modes/entertainment/suggest", json={"budget": 1000}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    preview = resp.json()
    session = await new_session(client, headers, "entertainment", 1000)
    for field in ("suggested_base", "suggested_press", "suggested_max", "session_budget"):
        assert preview[field] == session[field], field

    strike = await client.post(f"{API}/modes/strike/suggest", json={"budget": 555}, headers=headers)
    assert strike.json()["session_budget"] == 890.0
