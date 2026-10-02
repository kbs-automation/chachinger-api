import uuid

import pytest
from sqlalchemy import func, select

from app.core.security import hash_password
from app.models import AdminAuditLog, User
from app.services import audit
from tests.helpers import API, register


async def _admin_headers(client, db) -> dict[str, str]:
    db.add(
        User(
            email="admin@cha3535.com",
            password_hash=hash_password("AdminPass1!"),
            player_number="#00001",
            is_admin=True,
        )
    )
    await db.commit()
    resp = await client.post(
        f"{API}/admin/auth/login", json={"email": "admin@cha3535.com", "password": "AdminPass1!"}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _target_user_id(client, db) -> uuid.UUID:
    await register(client, "target@example.com")
    return await db.scalar(select(User.id).where(User.email == "target@example.com"))


async def _audit_count(db) -> int:
    return int(await db.scalar(select(func.count()).select_from(AdminAuditLog)))


async def test_flag_writes_audit_row(client, db):
    headers = await _admin_headers(client, db)
    target = await _target_user_id(client, db)

    resp = await client.patch(f"{API}/admin/users/{target}/flag", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_flagged"] is True

    row = await db.scalar(select(AdminAuditLog))
    assert (row.action, row.target_type, row.target_id) == ("FLAG", "user", str(target))
    assert row.payload == {"before": {"is_flagged": False}, "after": {"is_flagged": True}}


async def test_audit_failure_rolls_back_the_admin_write(client, db, monkeypatch):
    headers = await _admin_headers(client, db)
    target = await _target_user_id(client, db)

    async def broken_audit(*args, **kwargs):
        raise RuntimeError("audit log unavailable")

    monkeypatch.setattr(audit, "record_admin_action", broken_audit)
    with pytest.raises(RuntimeError):
        await client.patch(f"{API}/admin/users/{target}/flag", headers=headers)

    db.expire_all()
    user = await db.get(User, target)
    assert user.is_flagged is False
    assert await _audit_count(db) == 0


async def test_mode_update_is_audited_and_zone_map_redacted(client, db):
    headers = await _admin_headers(client, db)

    gap = [{"s": 1, "e": 10, "t": "base"}, {"s": 12, "e": 96, "t": "press"}]
    bad = await client.patch(f"{API}/admin/modes/strike", json={"zone_map": gap}, headers=headers)
    assert bad.status_code == 422
    assert await _audit_count(db) == 0

    good_map = [{"s": 1, "e": 48, "t": "max"}, {"s": 49, "e": 96, "t": "base"}]
    resp = await client.patch(
        f"{API}/admin/modes/strike",
        json={"zone_map": good_map, "baseline_max": 35},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert "zone_map" not in resp.json()
    assert resp.json()["zone_count"] == 2

    log = (await client.get(f"{API}/admin/audit-log", headers=headers)).json()
    assert log["total"] == 1
    entry = log["items"][0]
    assert entry["action"] == "MODE_UPDATE"
    assert entry["payload"]["after"]["zone_map"]["redacted"] is True
    assert entry["payload"]["after"]["baseline_max"] == 35.0


async def test_config_update_is_audited(client, db):
    headers = await _admin_headers(client, db)
    resp = await client.patch(
        f"{API}/admin/config", json={"values": {"maintenance_mode": True}}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["values"]["maintenance_mode"] is True
    row = await db.scalar(select(AdminAuditLog))
    assert row.action == "CONFIG_UPDATE"

    user_headers = await register(client)
    blocked = await client.post(
        f"{API}/sessions", json={"p1_mode": "entertainment", "budget": 500}, headers=user_headers
    )
    assert blocked.status_code == 503


async def test_admin_endpoints_reject_user_tokens(client):
    user_headers = await register(client)
    resp = await client.get(f"{API}/admin/dashboard", headers=user_headers)
    assert resp.status_code in (401, 403)
