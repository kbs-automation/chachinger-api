"""Stripe Billing: plans, Checkout, Customer Portal, idempotent webhook processing."""

import json
import uuid
from typing import Any

import stripe
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import SubscriptionLog, User
from app.services.errors import DomainError

PLANS: list[dict[str, Any]] = [
    {
        "tier": "vip",
        "name": "VIP",
        "tier_label": "TIER 1",
        "badge": "ENTRY",
        "price_cents": 999,
        "features": [
            "Play-1 full command map",
            "Bet setup & machine confirmation",
            "Basic session history",
            "Zone map (Play-1)",
        ],
    },
    {
        "tier": "black",
        "name": "BLACK",
        "tier_label": "TIER 2",
        "badge": "POPULAR",
        "price_cents": 2499,
        "features": [
            "All 6 plays + cycle logic",
            "Density map readouts",
            "Block map & pocket zones",
            "Session protection alerts",
        ],
    },
    {
        "tier": "elite",
        "name": "ELITE",
        "tier_label": "TIER 3",
        "badge": "PREMIUM",
        "price_cents": 4999,
        "features": [
            "Full engine — all plays & cycles",
            "Advanced sequence analytics",
            "Reconstruction intelligence",
            "Multi-session tracking",
            "Performance intelligence",
        ],
    },
    {
        "tier": "diamond",
        "name": "DIAMOND",
        "tier_label": "TIER 4",
        "badge": "ULTIMATE",
        "price_cents": 9999,
        "features": [
            "Everything in Elite",
            "Deep-zone 100+ maps",
            "Historical opportunity map",
            "Priority support",
            "Early feature access",
        ],
    },
]
PRICE_CENTS = {p["tier"]: p["price_cents"] for p in PLANS}

_STATUS_MAP = {
    "active": "active",
    "trialing": "trialing",
    "past_due": "past_due",
    "unpaid": "past_due",
    "incomplete": "past_due",
    "canceled": "canceled",
    "incomplete_expired": "canceled",
    "paused": "canceled",
}
SUBSCRIPTION_EVENTS = {
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
}


def list_plans() -> list[dict[str, Any]]:
    trial_days = get_settings().trial_days
    return [{**p, "interval": "month", "trial_days": trial_days} for p in PLANS]


def _client() -> stripe.StripeClient:
    key = get_settings().stripe_secret_key
    if not key:
        raise DomainError(503, "billing_unavailable", "Billing is not configured")
    return stripe.StripeClient(key)


async def create_checkout(db: AsyncSession, user: User, tier: str) -> str:
    settings = get_settings()
    price_id = settings.stripe_price_ids.get(tier)
    if not price_id:
        raise DomainError(503, "billing_unavailable", f"No Stripe price configured for {tier}")
    client = _client()
    if not user.stripe_customer_id:
        customer = await client.v1.customers.create_async(
            params={"email": user.email, "metadata": {"user_id": str(user.id)}}
        )
        user.stripe_customer_id = customer.id
        await db.commit()
    subscription_data: dict[str, Any] = {"metadata": {"user_id": str(user.id), "tier": tier}}
    if user.subscription_status is None and settings.trial_days > 0:
        subscription_data["trial_period_days"] = settings.trial_days
    session = await client.v1.checkout.sessions.create_async(
        params={
            "mode": "subscription",
            "customer": user.stripe_customer_id,
            "client_reference_id": str(user.id),
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": settings.checkout_success_url,
            "cancel_url": settings.checkout_cancel_url,
            "subscription_data": subscription_data,
            "metadata": {"user_id": str(user.id), "tier": tier},
        }
    )
    return str(session.url)


async def create_portal(user: User) -> str:
    if not user.stripe_customer_id:
        raise DomainError(409, "no_billing_account", "No billing account exists for this user")
    session = await _client().v1.billing_portal.sessions.create_async(
        params={"customer": user.stripe_customer_id, "return_url": get_settings().portal_return_url}
    )
    return str(session.url)


def verify_event(payload: bytes, sig_header: str | None) -> dict[str, Any]:
    secret = get_settings().stripe_webhook_secret
    if not secret:
        raise DomainError(503, "billing_unavailable", "Webhook secret is not configured")
    if not sig_header:
        raise DomainError(400, "missing_signature", "Stripe-Signature header is required")
    try:
        stripe.WebhookSignature.verify_header(payload.decode("utf-8"), sig_header, secret)
        return json.loads(payload)
    except (stripe.SignatureVerificationError, ValueError, UnicodeDecodeError) as exc:
        raise DomainError(400, "invalid_signature", "Invalid Stripe signature") from exc


def _tier_for_price(price_id: str | None) -> str | None:
    if not price_id:
        return None
    for tier, configured in get_settings().stripe_price_ids.items():
        if configured and configured == price_id:
            return tier
    return None


async def _find_user(db: AsyncSession, obj: dict[str, Any]) -> User | None:
    customer = obj.get("customer")
    if isinstance(customer, str):
        user = await db.scalar(select(User).where(User.stripe_customer_id == customer))
        if user is not None:
            return user
    user_id = (obj.get("metadata") or {}).get("user_id") or obj.get("client_reference_id")
    if user_id:
        try:
            return await db.get(User, uuid.UUID(str(user_id)))
        except ValueError:
            return None
    return None


async def handle_event(db: AsyncSession, event: dict[str, Any]) -> str:
    event_id = str(event["id"])
    if await db.scalar(
        select(SubscriptionLog.id).where(SubscriptionLog.stripe_event_id == event_id)
    ):
        return "duplicate"

    event_type = str(event["type"])
    obj: dict[str, Any] = event.get("data", {}).get("object", {}) or {}
    user = await _find_user(db, obj)
    old_tier = user.tier if user else None
    amount_cents: int | None = None

    if event_type in SUBSCRIPTION_EVENTS:
        items = (obj.get("items") or {}).get("data") or []
        price = items[0].get("price", {}) if items else {}
        amount_cents = price.get("unit_amount")
        tier = _tier_for_price(price.get("id")) or (obj.get("metadata") or {}).get("tier")
        status = _STATUS_MAP.get(str(obj.get("status")), "canceled")
        if event_type == "customer.subscription.deleted":
            status = "canceled"
        if user is not None:
            if not user.stripe_customer_id and isinstance(obj.get("customer"), str):
                user.stripe_customer_id = obj["customer"]
            user.subscription_status = status
            if tier in PRICE_CENTS and status in ("active", "trialing"):
                user.tier = tier
    elif event_type == "checkout.session.completed":
        amount_cents = obj.get("amount_total")
        if (
            user is not None
            and not user.stripe_customer_id
            and isinstance(obj.get("customer"), str)
        ):
            user.stripe_customer_id = obj["customer"]
    elif event_type == "invoice.payment_failed":
        amount_cents = obj.get("amount_due")
        if user is not None:
            user.subscription_status = "past_due"
    elif event_type == "invoice.paid":
        amount_cents = obj.get("amount_paid")
        if user is not None and user.subscription_status == "past_due":
            user.subscription_status = "active"

    db.add(
        SubscriptionLog(
            user_id=user.id if user else None,
            stripe_event_id=event_id,
            event_type=event_type[:64],
            old_tier=old_tier,
            new_tier=user.tier if user else None,
            amount_cents=amount_cents,
        )
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return "duplicate"
    return "processed"
