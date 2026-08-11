"""Stripe multi-currency catalog for Veritas plans.

Checkout picks a Price ID by (tier, currency). Amounts here must match
what you create in the Stripe Dashboard.
"""

from __future__ import annotations

import os
from typing import Literal

Currency = Literal["USD", "EUR", "PLN", "RUB", "CNY"]
Tier = Literal["premium", "ultra", "ultra_lifetime"]

CURRENCIES: tuple[Currency, ...] = ("USD", "EUR", "PLN", "RUB", "CNY")

# Exact sticker amounts to create in Stripe (one Price per cell).
CATALOG: dict[Tier, dict[Currency, dict[str, float | str]]] = {
    "premium": {
        "USD": {"amount": 5.99, "label": "$5.99 / mo"},
        "EUR": {"amount": 5.49, "label": "€5.49 / mo"},
        "PLN": {"amount": 20.00, "label": "20 zł / mo"},
        "RUB": {"amount": 290.0, "label": "290 ₽ / mo"},
        "CNY": {"amount": 24.00, "label": "¥24 / mo"},
    },
    "ultra": {
        "USD": {"amount": 16.99, "label": "$16.99 / mo"},
        "EUR": {"amount": 14.99, "label": "€14.99 / mo"},
        "PLN": {"amount": 57.00, "label": "57 zł / mo"},
        "RUB": {"amount": 820.0, "label": "820 ₽ / mo"},
        "CNY": {"amount": 68.00, "label": "¥68 / mo"},
    },
    "ultra_lifetime": {
        "USD": {"amount": 79.00, "label": "$79 once"},
        "EUR": {"amount": 69.00, "label": "€69 once"},
        "PLN": {"amount": 265.0, "label": "265 zł once"},
        "RUB": {"amount": 3800.0, "label": "3800 ₽ once"},
        "CNY": {"amount": 315.0, "label": "¥315 once"},
    },
}

# Env keys: STRIPE_PRICE_PREMIUM_USD, STRIPE_PRICE_ULTRA_PLN, ...
# Legacy fallbacks: STRIPE_PRICE_ID / _ULTRA / _ULTRA_LIFETIME → USD
_ENV_TIER = {
    "premium": "PREMIUM",
    "ultra": "ULTRA",
    "ultra_lifetime": "ULTRA_LIFETIME",
}

_COUNTRY_CURRENCY: dict[str, Currency] = {
    "US": "USD",
    "DE": "EUR",
    "FR": "EUR",
    "IT": "EUR",
    "ES": "EUR",
    "NL": "EUR",
    "IE": "EUR",
    "PT": "EUR",
    "GR": "EUR",
    "AT": "EUR",
    "BE": "EUR",
    "FI": "EUR",
    "PL": "PLN",
    "RU": "RUB",
    "CN": "CNY",
    "TW": "CNY",
    "HK": "CNY",
}


def currency_for_country(country: str | None) -> Currency:
    if not country:
        return "USD"
    return _COUNTRY_CURRENCY.get(country.upper(), "USD")


def currency_from_accept_language(header: str | None) -> Currency | None:
    """Map browser language to catalog currency (no user picker)."""
    if not header:
        return None
    # e.g. "ru-RU,ru;q=0.9,en;q=0.8"
    primary = header.split(",")[0].strip().lower()
    lang = primary.split("-")[0]
    region = primary.split("-")[1].upper() if "-" in primary else ""
    if region and region in _COUNTRY_CURRENCY:
        return _COUNTRY_CURRENCY[region]
    lang_map: dict[str, Currency] = {
        "ru": "RUB",
        "pl": "PLN",
        "zh": "CNY",
        "de": "EUR",
        "fr": "EUR",
        "es": "EUR",
        "it": "EUR",
        "nl": "EUR",
        "pt": "EUR",
        "el": "EUR",
        "fi": "EUR",
        "en": "USD",
    }
    return lang_map.get(lang)


def detect_checkout_currency(
    *,
    country_header: str | None = None,
    accept_language: str | None = None,
) -> Currency:
    """
    Regional price lock: geo/country header first, then Accept-Language.
    Never trust a client-submitted currency (prevents picking cheap RUB/CNY).
    """
    if country_header:
        code = country_header.strip().upper()
        if len(code) >= 2:
            return currency_for_country(code[:2])
    from_lang = currency_from_accept_language(accept_language)
    if from_lang:
        return from_lang
    return "USD"


def currency_from_request_headers(headers: dict[str, str]) -> Currency:
    """Pick currency from proxy geo headers + Accept-Language."""
    lower = {k.lower(): v for k, v in headers.items()}
    country = (
        lower.get("cf-ipcountry")
        or lower.get("cloudfront-viewer-country")
        or lower.get("x-vercel-ip-country")
        or lower.get("x-country-code")
        or lower.get("x-geo-country")
    )
    if country and country.upper() in {"XX", "T1"}:
        country = None
    return detect_checkout_currency(
        country_header=country,
        accept_language=lower.get("accept-language"),
    )


def normalize_currency(value: str | None) -> Currency:
    code = (value or "USD").strip().upper()
    if code in CURRENCIES:
        return code  # type: ignore[return-value]
    return "USD"


def _legacy_usd(tier: Tier) -> str:
    if tier == "premium":
        return os.getenv("STRIPE_PRICE_ID", "").strip()
    if tier == "ultra":
        return os.getenv("STRIPE_PRICE_ID_ULTRA", "").strip()
    return os.getenv("STRIPE_PRICE_ID_ULTRA_LIFETIME", "").strip()


def price_id_for(tier: Tier, currency: Currency) -> str:
    env_tier = _ENV_TIER[tier]
    key = f"STRIPE_PRICE_{env_tier}_{currency}"
    value = os.getenv(key, "").strip()
    if value:
        return value
    if currency == "USD":
        return _legacy_usd(tier)
    # Fall back to USD price if regional missing (still charges USD)
    return _legacy_usd(tier)


def label_for(tier: Tier, currency: Currency) -> str:
    return str(CATALOG[tier][currency]["label"])


def amount_for(tier: Tier, currency: Currency) -> float:
    return float(CATALOG[tier][currency]["amount"])


def currency_options() -> list[dict[str, str]]:
    return [
        {"code": "USD", "name": "USD - US Dollar"},
        {"code": "EUR", "name": "EUR - Euro"},
        {"code": "PLN", "name": "PLN - Polish Zloty"},
        {"code": "RUB", "name": "RUB - Russian Ruble"},
        {"code": "CNY", "name": "CNY - Chinese Yuan"},
    ]
