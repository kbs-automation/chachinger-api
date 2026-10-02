import hashlib
import hmac
import json
import time

from sqlalchemy import func, select

from app.models import SubscriptionLog, User
from tests.helpers import API, register

SECRET = "whsec_test_secret"


def _signed(payload: bytes) -> dict[str, str]:
    ts = int(time.time())
    sig = hmac.new(SECRET.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return {"Stripe-Signature": f"t={ts},v1={sig}", "Content-Type": "application/json"}


async def test_same_event_twice_processes_once(client, db):
    headers = await register(client, "subscriber@example.com")
    user = await db.scalar(select(User).where(User.email == "subscriber@example.com"))
    user.stripe_customer_id = "cus_test_123"
    await db.commit()

    event = {
        "id": "evt_test_idempotent_1",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_123",
                "customer": "cus_test_123",
                "status": "active",
                "items": {"data": [{"price": {"id": "price_black_test", "unit_amount": 2499}}]},
            }
        },
    }
    payload = json.dumps(event).encode()

    first = await client.post(f"{API}/webhooks/stripe", content=payload, headers=_signed(payload))
    second = await client.post(f"{API}/webhooks/stripe", content=payload, headers=_signed(payload))
    assert first.status_code == 200 and first.json()["status"] == "processed"
    assert second.status_code == 200 and second.json()["status"] == "duplicate"

    db.expire_all()
    count = await db.scalar(
        select(func.count())
        .select_from(SubscriptionLog)
        .where(SubscriptionLog.stripe_event_id == "evt_test_idempotent_1")
    )
    assert count == 1
    log = await db.scalar(select(SubscriptionLog))
    assert (log.old_tier, log.new_tier, log.amount_cents) == ("vip", "black", 2499)

    me = (await client.get(f"{API}/auth/me", headers=headers)).json()
    assert (me["tier"], me["subscription_status"]) == ("black", "active")


async def test_invalid_signature_is_rejected(client):
    payload = json.dumps({"id": "evt_bad", "type": "invoice.paid", "data": {"object": {}}}).encode()
    resp = await client.post(
        f"{API}/webhooks/stripe",
        content=payload,
        headers={"Stripe-Signature": "t=1,v1=deadbeef", "Content-Type": "application/json"},
    )
    assert resp.status_code == 400
