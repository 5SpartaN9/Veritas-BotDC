import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# Public links (Discord /about, bot description)
SITE_URL = os.getenv(
    "SITE_URL",
    "https://5spartan9.github.io/Veritas-BotDC/",
).rstrip("/") + "/"
PANEL_URL = os.getenv(
    "PANEL_URL",
    os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/") + "/dashboard",
)

if not DISCORD_TOKEN:
    raise ValueError("Missing DISCORD_TOKEN in .env")
if not GOOGLE_API_KEY:
    raise ValueError("Missing GOOGLE_API_KEY in .env")
