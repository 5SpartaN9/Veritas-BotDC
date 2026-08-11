from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "1533047923829375056")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = os.getenv(
    "DISCORD_REDIRECT_URI",
    "http://127.0.0.1:8000/auth/callback",
)
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-me-veritas-dev-secret")
WEB_HOST = os.getenv("WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.getenv("WEB_PORT", "8000"))
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
SITE_URL = os.getenv(
    "SITE_URL",
    "https://5spartan9.github.io/Veritas-BotDC/",
).rstrip("/") + "/"
PANEL_URL = os.getenv("PANEL_URL", f"{PUBLIC_BASE_URL}/dashboard")

# Payments — Stripe (cards, BLIK via local methods, optional PayPal in Stripe Dashboard)
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")  # Premium recurring Price ID
STRIPE_PRICE_ID_ULTRA = os.getenv("STRIPE_PRICE_ID_ULTRA", "")  # Ultra recurring Price ID
STRIPE_PRICE_ID_ULTRA_LIFETIME = os.getenv(
    "STRIPE_PRICE_ID_ULTRA_LIFETIME", ""
)  # Ultra one-time Price ID (~$60 US reference)
PREMIUM_PRICE_LABEL = os.getenv("PREMIUM_PRICE_LABEL", "$4.99 / month")
ULTRA_PRICE_LABEL = os.getenv("ULTRA_PRICE_LABEL", "$14.99 / month")
ULTRA_LIFETIME_PRICE_LABEL = os.getenv(
    "ULTRA_LIFETIME_PRICE_LABEL", "$60 once · forever"
)

# Optional PayPal button / link (PayPal.me or hosted button URL)
PAYPAL_ME_URL = os.getenv("PAYPAL_ME_URL", "")
PAYPAL_BUTTON_URL = os.getenv("PAYPAL_BUTTON_URL", "")

API_BASE = "https://discord.com/api/v10"
OAUTH_AUTHORIZE = "https://discord.com/api/oauth2/authorize"
OAUTH_TOKEN = "https://discord.com/api/oauth2/token"
INVITE_URL = (
    f"https://discord.com/api/oauth2/authorize"
    f"?client_id={DISCORD_CLIENT_ID}"
    f"&permissions=36703232"
    f"&scope=bot%20applications.commands"
)

MANAGE_GUILD = 0x20
ADMINISTRATOR = 0x8

PAYMENTS_ENABLED = bool(STRIPE_SECRET_KEY and STRIPE_PRICE_ID)
