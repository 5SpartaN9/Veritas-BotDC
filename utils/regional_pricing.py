"""Regional sticker prices scaled by typical local income / PPP vs US.

Display estimates only — real charge must use Stripe billing / card country
so VPN + locale tricks cannot pick a cheaper tier.
"""

from __future__ import annotations

from dataclasses import dataclass

# Base list prices in USD (United States reference)
BASE_PREMIUM_USD = 4.99
BASE_ULTRA_USD = 14.99
BASE_ULTRA_LIFETIME_USD = 60.00

# Never show / aim below this share of US USD value (anti-dump floor)
MIN_INCOME_FACTOR = 0.48


@dataclass(frozen=True)
class RegionPrice:
    code: str
    name: str
    currency: str
    symbol: str
    # Income / PPP factor vs US (1.0 = US sticker). Lower = cheaper local price.
    income_factor: float
    # Approx FX: 1 USD → local units (display only; Stripe uses own rates later)
    fx: float


# Milder discounts than Steam-style bottoms — still fair, still profitable.
REGIONS: dict[str, RegionPrice] = {
    "US": RegionPrice("US", "United States", "USD", "$", 1.00, 1.00),
    "CA": RegionPrice("CA", "Canada", "CAD", "C$", 0.95, 1.37),
    "GB": RegionPrice("GB", "United Kingdom", "GBP", "£", 0.95, 0.79),
    "IE": RegionPrice("IE", "Ireland", "EUR", "€", 0.95, 0.92),
    "DE": RegionPrice("DE", "Germany", "EUR", "€", 0.92, 0.92),
    "FR": RegionPrice("FR", "France", "EUR", "€", 0.90, 0.92),
    "NL": RegionPrice("NL", "Netherlands", "EUR", "€", 0.94, 0.92),
    "SE": RegionPrice("SE", "Sweden", "SEK", "kr", 0.92, 10.5),
    "NO": RegionPrice("NO", "Norway", "NOK", "kr", 1.05, 10.7),
    "CH": RegionPrice("CH", "Switzerland", "CHF", "CHF", 1.10, 0.88),
    "AU": RegionPrice("AU", "Australia", "AUD", "A$", 0.95, 1.53),
    "NZ": RegionPrice("NZ", "New Zealand", "NZD", "NZ$", 0.90, 1.66),
    "JP": RegionPrice("JP", "Japan", "JPY", "¥", 0.88, 150.0),
    "KR": RegionPrice("KR", "South Korea", "KRW", "₩", 0.85, 1350.0),
    "SG": RegionPrice("SG", "Singapore", "SGD", "S$", 0.95, 1.34),
    "AE": RegionPrice("AE", "United Arab Emirates", "AED", "AED", 0.92, 3.67),
    # ~200 zł Lifetime at ~3.95 PLN/USD
    "PL": RegionPrice("PL", "Poland", "PLN", "zł", 0.85, 3.95),
    "CZ": RegionPrice("CZ", "Czechia", "CZK", "Kč", 0.82, 23.0),
    "HU": RegionPrice("HU", "Hungary", "HUF", "Ft", 0.72, 360.0),
    "RO": RegionPrice("RO", "Romania", "RON", "lei", 0.68, 4.6),
    "ES": RegionPrice("ES", "Spain", "EUR", "€", 0.85, 0.92),
    "IT": RegionPrice("IT", "Italy", "EUR", "€", 0.85, 0.92),
    "PT": RegionPrice("PT", "Portugal", "EUR", "€", 0.80, 0.92),
    "GR": RegionPrice("GR", "Greece", "EUR", "€", 0.75, 0.92),
    "TR": RegionPrice("TR", "Türkiye", "TRY", "₺", 0.55, 34.0),
    "UA": RegionPrice("UA", "Ukraine", "UAH", "₴", 0.50, 41.0),
    "BR": RegionPrice("BR", "Brazil", "BRL", "R$", 0.58, 5.5),
    "MX": RegionPrice("MX", "Mexico", "MXN", "MX$", 0.55, 17.5),
    "AR": RegionPrice("AR", "Argentina", "ARS", "AR$", 0.50, 950.0),
    "CL": RegionPrice("CL", "Chile", "CLP", "CLP", 0.62, 950.0),
    "IN": RegionPrice("IN", "India", "INR", "₹", 0.48, 84.0),
    "PH": RegionPrice("PH", "Philippines", "PHP", "₱", 0.50, 58.0),
    "ID": RegionPrice("ID", "Indonesia", "IDR", "Rp", 0.48, 16000.0),
    "VN": RegionPrice("VN", "Vietnam", "VND", "₫", 0.48, 25000.0),
    "TH": RegionPrice("TH", "Thailand", "THB", "฿", 0.55, 35.0),
    "MY": RegionPrice("MY", "Malaysia", "MYR", "RM", 0.62, 4.5),
    "ZA": RegionPrice("ZA", "South Africa", "ZAR", "R", 0.55, 18.5),
    "NG": RegionPrice("NG", "Nigeria", "NGN", "₦", 0.48, 1550.0),
    "EG": RegionPrice("EG", "Egypt", "EGP", "E£", 0.48, 48.0),
}

DEFAULT_REGION = REGIONS["US"]


def get_region(code: str | None) -> RegionPrice:
    if not code:
        return DEFAULT_REGION
    region = REGIONS.get(code.upper(), DEFAULT_REGION)
    factor = max(region.income_factor, MIN_INCOME_FACTOR)
    if factor == region.income_factor:
        return region
    return RegionPrice(
        region.code,
        region.name,
        region.currency,
        region.symbol,
        factor,
        region.fx,
    )


def _nice_round(amount: float, currency: str) -> float:
    """Round to familiar retail endings for the currency."""
    if currency in {"JPY", "KRW", "VND", "IDR", "HUF", "CLP", "ARS", "NGN"}:
        if amount >= 10000:
            return float(int(round(amount / 1000) * 1000))
        if amount >= 1000:
            return float(int(round(amount / 100) * 100))
        return float(int(round(amount / 10) * 10))
    if amount >= 100:
        return float(int(round(amount)))
    if amount >= 20:
        return round(amount * 2) / 2
    whole = int(amount)
    if whole < 1:
        return round(amount, 2)
    return whole + 0.99


def local_amount(base_usd: float, region: RegionPrice) -> float:
    factor = max(region.income_factor, MIN_INCOME_FACTOR)
    raw = base_usd * factor * region.fx
    return _nice_round(raw, region.currency)


def format_money(amount: float, region: RegionPrice) -> str:
    currency = region.currency
    if currency in {"JPY", "KRW", "VND", "IDR", "HUF", "CLP", "ARS", "NGN"}:
        n = f"{int(amount):,}".replace(",", " ")
        if currency == "JPY":
            return f"¥{n}"
        if currency == "KRW":
            return f"₩{n}"
        if currency == "VND":
            return f"{n}₫"
        if currency == "IDR":
            return f"Rp {n}"
        if currency == "HUF":
            return f"{n} Ft"
        if currency == "CLP":
            return f"CLP {n}"
        if currency == "ARS":
            return f"AR$ {n}"
        return f"₦{n}"

    if currency == "PLN":
        return f"{amount:.2f} zł".replace(".", ",")
    if currency == "EUR":
        return f"€{amount:.2f}"
    if currency == "GBP":
        return f"£{amount:.2f}"
    if currency == "USD":
        return f"${amount:.2f}"
    if region.symbol in {"$", "C$", "A$", "NZ$", "MX$", "S$", "R$"}:
        return f"{region.symbol}{amount:.2f}"
    return f"{amount:.2f} {region.symbol}"


def price_labels(code: str | None = "US") -> dict[str, str]:
    region = get_region(code)
    premium = local_amount(BASE_PREMIUM_USD, region)
    ultra = local_amount(BASE_ULTRA_USD, region)
    lifetime = local_amount(BASE_ULTRA_LIFETIME_USD, region)
    return {
        "region": region.code,
        "region_name": region.name,
        "currency": region.currency,
        "premium": f"{format_money(premium, region)} / mo",
        "ultra": f"{format_money(ultra, region)} / mo",
        "lifetime": f"{format_money(lifetime, region)} once",
        "lifetime_note": "Ultra Premium forever — one payment, no subscription",
        "premium_usd_ref": f"${BASE_PREMIUM_USD:.2f}",
        "ultra_usd_ref": f"${BASE_ULTRA_USD:.2f}",
        "lifetime_usd_ref": f"${BASE_ULTRA_LIFETIME_USD:.0f}",
    }


def regions_for_select() -> list[tuple[str, str]]:
    return sorted(((r.code, r.name) for r in REGIONS.values()), key=lambda x: x[1])
