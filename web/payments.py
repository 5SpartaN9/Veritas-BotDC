from __future__ import annotations

import logging
from typing import Any

import stripe

from utils.settings import settings_store
from web.config import (
    PUBLIC_BASE_URL,
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
)
from web.stripe_catalog import (
    Currency,
    Tier,
    normalize_currency,
    price_id_for,
)

logger = logging.getLogger("veritas.payments")

VALID_TIERS = {"premium", "ultra", "ultra_lifetime"}


def stripe_ready(tier: str = "premium", currency: str = "USD") -> bool:
    if not STRIPE_SECRET_KEY:
        return False
    if tier not in VALID_TIERS:
        tier = "premium"
    cur = normalize_currency(currency)
    return bool(price_id_for(tier, cur))  # type: ignore[arg-type]


def create_checkout_session(
    *,
    guild_id: str,
    guild_name: str,
    user_id: str,
    user_email: str | None = None,
    tier: str = "premium",
    currency: str = "USD",
) -> str:
    """Return Stripe Checkout URL for Premium, Ultra, or Ultra Lifetime."""
    if tier not in VALID_TIERS:
        tier = "premium"
    cur: Currency = normalize_currency(currency)
    if not stripe_ready(tier, cur):
        raise RuntimeError("Stripe is not configured for this plan/currency")

    price_id = price_id_for(tier, cur)  # type: ignore[arg-type]
    mode = "payment" if tier == "ultra_lifetime" else "subscription"
    if not price_id:
        raise RuntimeError("Stripe price is not configured")

    stripe.api_key = STRIPE_SECRET_KEY
    success = (
        f"{PUBLIC_BASE_URL}/dashboard/{guild_id}"
        f"?paid=1&tier={tier}&session_id={{CHECKOUT_SESSION_ID}}"
    )
    cancel = f"{PUBLIC_BASE_URL}/dashboard/{guild_id}?canceled=1"

    meta = {
        "guild_id": guild_id,
        "guild_name": guild_name[:80],
        "discord_user_id": user_id,
        "plan_tier": tier,
        "currency": cur,
    }

    params: dict[str, Any] = {
        "mode": mode,
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success,
        "cancel_url": cancel,
        "client_reference_id": guild_id,
        "metadata": meta,
        "allow_promotion_codes": True,
    }
    if mode == "subscription":
        params["subscription_data"] = {
            "metadata": {
                "guild_id": guild_id,
                "discord_user_id": user_id,
                "plan_tier": tier,
                "currency": cur,
            }
        }
    else:
        params["payment_intent_data"] = {
            "metadata": {
                "guild_id": guild_id,
                "discord_user_id": user_id,
                "plan_tier": tier,
                "currency": cur,
            }
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


def cancel_subscription_to_free(guild_id: int) -> dict[str, str]:
    """Cancel Stripe subscription (if any) and set the guild to Free."""
    data = settings_store.get_guild_plan(guild_id)
    if data.get("lifetime"):
        raise RuntimeError("Ultra Lifetime cannot be downgraded")

    sub_id = data.get("stripe_subscription_id")
    if sub_id and STRIPE_SECRET_KEY:
        stripe.api_key = STRIPE_SECRET_KEY
        try:
            stripe.Subscription.cancel(str(sub_id))
        except Exception as exc:
            # Fallback for older stripe SDK names / already-canceled subs.
            logger.warning("Stripe cancel failed for %s: %s", sub_id, exc)
            try:
                stripe.Subscription.delete(str(sub_id))
            except Exception as exc2:
                logger.warning("Stripe delete failed for %s: %s", sub_id, exc2)

    if not settings_store.clear_plan_to_free(guild_id):
        raise RuntimeError("Could not switch this server to Free")
    return {"ok": "free", "guild_id": str(guild_id)}


def handle_webhook(payload: bytes, signature: str | None) -> dict[str, str]:
    stripe.api_key = STRIPE_SECRET_KEY
    secret = (STRIPE_WEBHOOK_SECRET or "").strip()
    if secret:
        if not signature:
            raise ValueError("Missing Stripe signature")
        event = stripe.Webhook.construct_event(payload, signature, secret)
    else:
        import json

        event = stripe.Event.construct_from(json.loads(payload), STRIPE_SECRET_KEY)

    etype = event["type"]
    data = event["data"]["object"]
    return _apply_checkout_or_subscription(etype, data)


def activate_from_checkout_session(session_id: str) -> dict[str, str]:
    """Fallback when webhooks fail: unlock plan from Checkout Session id."""
    if not STRIPE_SECRET_KEY or not session_id:
        return {"ok": "skipped"}
    stripe.api_key = STRIPE_SECRET_KEY
    session = stripe.checkout.Session.retrieve(session_id)
    data = session.to_dict() if hasattr(session, "to_dict") else dict(session)
    return _apply_checkout_or_subscription("checkout.session.completed", data)


def _apply_checkout_or_subscription(etype: str, data: dict) -> dict[str, str]:
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
            lifetime = tier == "ultra_lifetime"
            settings_store.set_premium(
                int(guild_id),
                True,
                ultra=(tier in {"ultra", "ultra_lifetime"}),
                lifetime=lifetime,
                stripe_customer_id=str(customer_id) if customer_id else None,
                stripe_subscription_id=(
                    None if lifetime else (str(sub_id) if sub_id else None)
                ),
            )
            logger.info("Plan %s ON for guild %s via %s", tier, guild_id, etype)
            return {"ok": "premium_on", "guild_id": str(guild_id), "tier": tier}

    if etype in {
        "customer.subscription.deleted",
        "invoice.payment_failed",
    }:
        guild_id = _guild_from_object(data)
        if etype == "customer.subscription.deleted" and guild_id:
            settings_store.set_premium(int(guild_id), False)
            logger.info("Premium OFF for guild %s (if not lifetime)", guild_id)
            return {"ok": "premium_off", "guild_id": str(guild_id)}

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
    if tier in {"ultra_lifetime", "lifetime", "ultra-lifetime"}:
        return "ultra_lifetime"
    if tier == "ultra":
        return "ultra"
    return "premium"
