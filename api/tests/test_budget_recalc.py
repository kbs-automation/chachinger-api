from tests.helpers import API, begin_play, new_session, register


async def test_session_budget_covers_baseline_exposure_at_creation(client):
    headers = await register(client)
    session = await new_session(client, headers, "strike", 555)
    # Strike baseline over the full 96-click map: 15×$30 + 7×$10 + 74×$5 = $890.
    assert session["session_budget"] == 890.0
    assert session["current_balance"] == 890.0
    assert (session["suggested_base"], session["suggested_press"], session["suggested_max"]) == (
        5.0,
        10.0,
        30.0,
    )


async def test_bets_above_baseline_raise_session_budget_to_96_click_exposure(client):
    headers = await register(client)
    session = await new_session(client, headers, "strike", 555)
    sid = session["session_id"]

    resp = await client.post(
        f"{API}/sessions/{sid}/recalculate-budget",
        json={"base": 10, "press": 20, "max": 60},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # 15×$60 + 7×$20 + 74×$10 = $1,780.
    assert body == {
        "required_budget": 1780.0,
        "adjusted": True,
        "new_budget": 1780.0,
        "current_balance": 1780.0,
    }
    state = (await client.get(f"{API}/sessions/{sid}", headers=headers)).json()
    assert state["session_budget"] == 1780.0

    lower = await client.post(
        f"{API}/sessions/{sid}/recalculate-budget",
        json={"base": 5, "press": 10, "max": 30},
        headers=headers,
    )
    assert lower.json()["adjusted"] is False
    assert lower.json()["new_budget"] == 1780.0

    play = await begin_play(client, headers, sid, 10, 20, 60)
    assert play["click_cap"] == 96


async def test_play_start_requires_recalculation_when_bets_exceed_budget(client):
    headers = await register(client)
    session = await new_session(client, headers, "strike", 555)
    resp = await client.post(
        f"{API}/sessions/{session['session_id']}/plays",
        json={"confirmed_base": 10, "confirmed_press": 20, "confirmed_max": 60},
        headers=headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "budget_recalculation_required"
    assert resp.json()["detail"]["required_budget"] == 1780.0


async def test_mode_exposure_endpoint_matches_minimum_rules(client):
    headers = await register(client)
    resp = await client.post(
        f"{API}/modes/entertainment_plus/exposure",
        json={"base": 5, "press": 10, "max": 25},
        headers=headers,
    )
    # Entertainment+ baseline exposure is $1,245, below its $1,300 minimum.
    assert resp.json() == {
        "mode_id": "entertainment_plus",
        "exposure": 1245.0,
        "required_budget": 1300.0,
    }
