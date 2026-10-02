"""RULE 4 — no user endpoint accepts session_budget in its request body."""

from tests.helpers import API, new_session, register


def _resolve(schema: dict, components: dict) -> dict:
    ref = schema.get("$ref")
    return components[ref.rsplit("/", 1)[-1]] if ref else schema


async def test_openapi_request_bodies_never_accept_session_budget(client):
    spec = (await client.get("/openapi.json")).json()
    components = spec["components"]["schemas"]
    for path, ops in spec["paths"].items():
        if path.startswith(f"{API}/admin"):
            continue
        for method, op in ops.items():
            content = op.get("requestBody", {}).get("content", {})
            for media in content.values():
                schema = _resolve(media["schema"], components)
                props = schema.get("properties", {})
                assert "session_budget" not in props, f"{method.upper()} {path}"


async def test_session_budget_in_body_is_rejected(client):
    headers = await register(client)
    resp = await client.post(
        f"{API}/sessions",
        json={"p1_mode": "entertainment", "budget": 500, "session_budget": 99999},
        headers=headers,
    )
    assert resp.status_code == 422

    session = await new_session(client, headers, "entertainment", 500)
    sid = session["session_id"]
    for path, body in (
        (f"{API}/sessions/{sid}/recalculate-budget", {"base": 2, "press": 5, "max": 8}),
        (
            f"{API}/sessions/{sid}/plays",
            {"confirmed_base": 2, "confirmed_press": 5, "confirmed_max": 8},
        ),
    ):
        resp = await client.post(path, json={**body, "session_budget": 99999}, headers=headers)
        assert resp.status_code == 422, path

    state = (await client.get(f"{API}/sessions/{sid}", headers=headers)).json()
    assert state["session_budget"] == session["session_budget"]
