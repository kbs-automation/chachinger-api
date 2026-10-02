import uuid
from typing import Any

from httpx import AsyncClient

API = "/api/v1"


async def register(client: AsyncClient, email: str | None = None) -> dict[str, str]:
    email = email or f"player-{uuid.uuid4().hex[:10]}@example.com"
    resp = await client.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!"})
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def new_session(
    client: AsyncClient, headers: dict[str, str], mode: str = "entertainment", budget: float = 1000
) -> dict[str, Any]:
    resp = await client.post(
        f"{API}/sessions", json={"p1_mode": mode, "budget": budget}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def begin_play(
    client: AsyncClient,
    headers: dict[str, str],
    session_id: str,
    base: float,
    press: float,
    max_bet: float,
) -> dict[str, Any]:
    resp = await client.post(
        f"{API}/sessions/{session_id}/plays",
        json={"confirmed_base": base, "confirmed_press": press, "confirmed_max": max_bet},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def begin_suggested_play(
    client: AsyncClient, headers: dict[str, str], session: dict[str, Any]
) -> dict[str, Any]:
    return await begin_play(
        client,
        headers,
        session["session_id"],
        session["suggested_base"],
        session["suggested_press"],
        session["suggested_max"],
    )


async def spin(client: AsyncClient, headers: dict[str, str], play_id: str) -> dict[str, Any]:
    resp = await client.post(f"{API}/plays/{play_id}/spins", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def submit(
    client: AsyncClient, headers: dict[str, str], play_id: str, spin_id: str, result: str
) -> dict[str, Any]:
    resp = await client.post(
        f"{API}/plays/{play_id}/spins/{spin_id}/result", json={"result": result}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def keys_matching(obj: Any, needle: str) -> list[str]:
    """Every key anywhere in a JSON document that contains `needle` (case-insensitive)."""
    found: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if needle in k.lower():
                found.append(k)
            found.extend(keys_matching(v, needle))
    elif isinstance(obj, list):
        for v in obj:
            found.extend(keys_matching(v, needle))
    return found
