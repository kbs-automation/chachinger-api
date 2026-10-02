"""RULE 1 — click_number must never appear in any user-facing response. Runs on every commit."""

from tests.helpers import (
    API,
    begin_suggested_play,
    keys_matching,
    new_session,
    register,
    spin,
    submit,
)

ADMIN_SCHEMAS_WITH_CLICK_DATA = {"AdminSpinOut", "AdminPlayOut", "LiveSessionOut", "AdminModeOut"}


async def test_spin_responses_never_contain_click_keys(client):
    headers = await register(client)
    session = await new_session(client, headers, "strike", 555)
    play = await begin_suggested_play(client, headers, session)

    responses = []
    for _ in range(96):
        responses.append(await spin(client, headers, play["play_id"]))
    over_cap = await client.post(f"{API}/plays/{play['play_id']}/spins", headers=headers)
    responses.append(over_cap.json())

    assert responses[-1]["redirect"] == "hard_exit"
    for body in responses:
        assert keys_matching(body, "click") == [], body


async def test_other_user_endpoints_hide_click_number(client):
    headers = await register(client)
    session = await new_session(client, headers)
    play = await begin_suggested_play(client, headers, session)
    s = await spin(client, headers, play["play_id"])
    result = await submit(client, headers, play["play_id"], s["spin_id"], "3x")

    bodies = [
        session,
        play,
        result,
        (await client.get(f"{API}/plays/{play['play_id']}", headers=headers)).json(),
        (await client.get(f"{API}/sessions/{session['session_id']}", headers=headers)).json(),
        (await client.get(f"{API}/sessions", headers=headers)).json(),
        (await client.get(f"{API}/modes")).json(),
    ]
    for body in bodies:
        assert keys_matching(body, "click_number") == [], body
        assert keys_matching(body, "total_clicks") == [], body
        assert keys_matching(body, "zone_map") == [], body


async def test_openapi_user_schemas_do_not_declare_click_number(client):
    schemas = (await client.get("/openapi.json")).json()["components"]["schemas"]
    for name, schema in schemas.items():
        if name in ADMIN_SCHEMAS_WITH_CLICK_DATA:
            continue
        props = schema.get("properties", {})
        assert "click_number" not in props, name
        assert "total_clicks" not in props, name
        assert "zone_map" not in props or name == "ModeUpdateRequest", name
