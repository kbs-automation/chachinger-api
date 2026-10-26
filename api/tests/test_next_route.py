from decimal import Decimal

from app.engine import routes
from app.models.base import ROUTE_IDS
from tests.helpers import API, begin_suggested_play, keys_matching, new_session, register, spin


def test_route_ids_match_the_engine():
    assert ROUTE_IDS == tuple(route.route_id for route in routes.ROUTES)


async def _finish_play(client, headers, session):
    play = await begin_suggested_play(client, headers, session)
    spun = await spin(client, headers, play["play_id"])
    result = await client.post(
        f"{API}/plays/{play['play_id']}/spins/{spun['spin_id']}/result",
        json={"result": "bonus", "win_amount": 50},
        headers=headers,
    )
    assert result.status_code == 200, result.text
    return result.json()


async def test_qualifying_result_offers_routes_without_click_data(client):
    headers = await register(client)
    session = await new_session(client, headers, "strike", 890)
    body = await _finish_play(client, headers, session)

    assert body["redirect"] == "next_play"
    offer = body["continuation"]
    assert offer["can_continue"] is True
    assert offer["block_reason"] is None
    assert (offer["completed_play_number"], offer["next_play_number"]) == (1, 2)
    assert offer["prompt"] == "Choose Play-2 Budget"
    assert offer["selected_route"] is None
    assert offer["reference"]["source"] == "session_budget"
    assert [card["route_id"] for card in offer["routes"]] == list(ROUTE_IDS)
    assert offer["routes"][0]["heading"] == "EARLY POCKET DETECTED"
    assert "pocket only" in offer["routes"][0]["detail"]
    assert offer["routes"][1]["heading"] == "MID POCKETS DETECTED"
    exposures = [card["exposure_pct"] for card in offer["routes"]]
    risks = [card["risk_pct"] for card in offer["routes"]]
    assert exposures == sorted(exposures)
    assert exposures[0] < exposures[-1]
    assert risks[0] < risks[-1]
    assert keys_matching(offer, "click") == []

    budget = Decimal(str(offer["reference"]["budget"]))
    base, press, max_bet = (Decimal(str(offer["reference"][name])) for name in ("base", "press", "max"))
    wager = routes.route_wager("early", base, press, max_bet)
    assert offer["routes"][0]["exposure_pct"] == routes.percent(wager, budget)


async def test_selected_route_limits_the_next_play_and_can_be_repriced(client):
    headers = await register(client)
    session = await new_session(client, headers, "strike", 890)
    sid = session["session_id"]
    await _finish_play(client, headers, session)

    blocked = await client.post(
        f"{API}/sessions/{sid}/plays",
        json={"confirmed_base": 4, "confirmed_press": 10, "confirmed_max": 15},
        headers=headers,
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "route_required"

    quoted = await client.post(
        f"{API}/sessions/{sid}/next-route/quote",
        json={"budget": 400, "base": 2, "press": 4, "max": 6},
        headers=headers,
    )
    assert quoted.status_code == 200, quoted.text
    quote = quoted.json()
    assert quote["reference"]["source"] == "quoted_bets"
    assert quote["reference"]["budget"] == 400.0
    assert quote["routes"][0]["exposure_pct"] != (
        await client.get(f"{API}/sessions/{sid}/next-route", headers=headers)
    ).json()["routes"][0]["exposure_pct"]

    chosen = await client.post(
        f"{API}/sessions/{sid}/next-route", json={"route_id": "early"}, headers=headers
    )
    assert chosen.json()["selected_route"] == "early"
    state = (await client.get(f"{API}/sessions/{sid}", headers=headers)).json()
    assert state["selected_route"] == "early"

    play = await client.post(
        f"{API}/sessions/{sid}/plays",
        json={"confirmed_base": 4, "confirmed_press": 10, "confirmed_max": 15},
        headers=headers,
    )
    assert play.status_code == 201, play.text
    assert play.json()["click_cap"] == routes.get_route("early").end_click
    assert (await client.get(f"{API}/sessions/{sid}", headers=headers)).json()["selected_route"] is None


async def test_manual_exit_cancels_a_pending_route(client):
    headers = await register(client)
    session = await new_session(client, headers, "entertainment", 1000)
    sid = session["session_id"]
    await _finish_play(client, headers, session)
    await client.post(
        f"{API}/sessions/{sid}/next-route", json={"route_id": "deep"}, headers=headers
    )
    ended = await client.post(f"{API}/sessions/{sid}/end", headers=headers)
    assert ended.status_code == 200, ended.text
    assert ended.json()["selected_route"] is None
    offer = (await client.get(f"{API}/sessions/{sid}/next-route", headers=headers)).json()
    assert offer["can_continue"] is False
    assert offer["block_reason"] == "session_not_active"
    assert offer["routes"] == []


async def test_routes_are_unavailable_before_a_play_finishes(client):
    headers = await register(client)
    session = await new_session(client, headers, "entertainment", 500)
    offer = (await client.get(f"{API}/sessions/{session['session_id']}/next-route", headers=headers)).json()
    assert offer == {
            "can_continue": False,
            "block_reason": "no_completed_play",
            "completed_play_number": None,
            "next_play_number": None,
            "next_cycle_number": None,
            "prompt": None,
            "selected_route": None,
            "reference": None,
            "routes": [],
            "decision": None,
        }
