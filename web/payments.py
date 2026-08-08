from __future__ import annotations

import logging
from typing import Any

import stripe

from utils.settings import settings_store
from web.config import (
    PUBLIC_BASE_URL,
    STRIPE_PRICE_ID,
    STRIPE_PRICE_ID_ULTRA,
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
)

logger = logging.getLogger("veritas.payments")


def stripe_ready(tier: str = "premium") -> bool:
    if not STRIPE_SECRET_KEY:
        return False
    if tier == "ultra":
        return bool(STRIPE_PRICE_ID_ULTRA or STRIPE_PRICE_ID)
    return bool(STRIPE_PRICE_ID)


def create_checkout_session(
    *,
    guild_id: str,
    guild_name: str,
    user_id: str,
    user_email: str | None = None,
    tier: str = "premium",
) -> str:
    """Return Stripe Checkout URL for Premium or Ultra subscription."""
    if tier not in {"premium", "ultra"}:
        tier = "premium"
    if not stripe_ready(tier):
        raise RuntimeError("Stripe is not configured")

    price_id = STRIPE_PRICE_ID_ULTRA if tier == "ultra" and STRIPE_PRICE_ID_ULTRA else STRIPE_PRICE_ID
    if not price_id:
        raise RuntimeError("Stripe price is not configured")

    stripe.api_key = STRIPE_SECRET_KEY
    success = f"{PUBLIC_BASE_URL}/dashboard/{guild_id}?paid=1&tier={tier}"
    cancel = f"{PUBLIC_BASE_URL}/dashboard/{guild_id}?canceled=1"

    params: dict[str, Any] = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success,
        "cancel_url": cancel,
        "client_reference_id": guild_id,
        "metadata": {
            "guild_id": guild_id,
            "guild_name": guild_name[:80],
            "discord_user_id": user_id,
            "plan_tier": tier,
        },
        "subscription_data": {
            "metadata": {
                "guild_id": guild_id,
                "discord_user_id": user_id,
                "plan_tier": tier,
            }
        },
        "allow_promotion_codes": True,
    }
    if user_email:
        params["customer_email"] = user_email

    session = stripe.checkout.Session.create(**params)
    if not session.url:
        raise RuntimeError("Stripe did not return a checkout URL")
    return session.url


def create_billing_portal(*, customer_id: str, guild_id: str) -> str:
    stripe.api_key = STRIPE_SECRET_KEY
    portal = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{PUBLIC_BASE_URL}/dashboard/{guild_id}",
    )
    return portal.url


def handle_webhook(payload: bytes, signature: str | None) -> dict[str, str]:
    stripe.api_key = STRIPE_SECRET_KEY
    if STRIPE_WEBHOOK_SECRET:
        if not signature:
            raise ValueError("Missing Stripe signature")
        event = stripe.Webhook.construct_event(
            payload, signature, STRIPE_WEBHOOK_SECRET
        )
    else:
        import json

        event = stripe.Event.construct_from(json.loads(payload), STRIPE_SECRET_KEY)

    etype = event["type"]
    data = event["data"]["object"]

    if etype in {
        "checkout.session.completed",
        "customer.subscription.created",
        "customer.subscription.updated",
    }:
        guild_id = _guild_from_object(data)
        customer_id = data.get("customer")
        sub_id = data.get("subscription") or data.get("id")
        status = data.get("status", "active")
        tier = _tier_from_object(data)
        if guild_id and status in {"active", "trialing", "complete", None, ""}:
            payment_status = data.get("payment_status")
            if payment_status and payment_status not in {"paid", "no_payment_required"}:
                return {"ok": "ignored_unpaid"}
            settings_store.set_premium(
                int(guild_id),
                True,
                ultra=(tier == "ultra"),
                stripe_customer_id=str(customer_id) if customer_id else None,
                stripe_subscription_id=str(sub_id) if sub_id else None,
            )
            logger.info("Plan %s ON for guild %s via %s", tier, guild_id, etype)
            return {"ok": "premium_on", "guild_id": guild_id, "tier": tier}

    if etype in {
        "customer.subscription.deleted",
        "invoice.payment_failed",
    }:
        guild_id = _guild_from_object(data)
        if etype == "customer.subscription.deleted" and guild_id:
            settings_store.set_premium(int(guild_id), False)
            logger.info("Premium OFF for guild %s", guild_id)
            return {"ok": "premium_off", "guild_id": guild_id}

    return {"ok": "ignored", "type": etype}


def _guild_from_object(data: dict) -> str | None:
    meta = data.get("metadata") or {}
    guild_id = meta.get("guild_id") or data.get("client_reference_id")
    if guild_id:
        return str(guild_id)
    return None


def _tier_from_object(data: dict) -> str:
    meta = data.get("metadata") or {}
    tier = str(meta.get("plan_tier") or "premium").lower()
    return "ultra" if tier == "ultra" else "premium"
