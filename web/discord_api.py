from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from web.config import API_BASE, DISCORD_TOKEN

_bot_guild_cache: set[str] = set()
_bot_guild_cache_at: float = 0.0
_BOT_GUILD_TTL = 90.0
_bot_guild_lock = asyncio.Lock()


async def discord_api(
    method: str,
    path: str,
    *,
    token: str,
    token_type: str = "Bearer",
    json: dict | None = None,
    data: dict | None = None,
    headers: dict | None = None,
    timeout: float = 8.0,
) -> Any:
    hdrs = {
        "Authorization": f"{token_type} {token}",
        **(headers or {}),
    }
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method,
                    f"{API_BASE}{path}",
                    headers=hdrs,
                    json=json,
                    data=data,
                )
                if response.status_code == 429:
                    retry_after = 0.6
                    try:
                        retry_after = float(response.json().get("retry_after", retry_after))
                    except Exception:
                        pass
                    await asyncio.sleep(min(retry_after, 2.0))
                    last_error = RuntimeError(
                        f"Discord API 429: {response.text[:300]}"
                    )
                    continue
                if response.status_code >= 400:
                    raise RuntimeError(
                        f"Discord API {response.status_code}: {response.text[:300]}"
                    )
                if response.status_code == 204:
                    return None
                return response.json()
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                await asyncio.sleep(0.4)
                continue
            raise
    assert last_error is not None
    raise last_error


async def fetch_bot_guild_ids(*, force: bool = False) -> set[str]:
    """Cached bot guild list — avoids Discord 429 wiping the dashboard."""
    global _bot_guild_cache, _bot_guild_cache_at

    if not DISCORD_TOKEN:
        return set()

    now = time.monotonic()
    if (
        not force
        and _bot_guild_cache_at
        and (now - _bot_guild_cache_at) < _BOT_GUILD_TTL
    ):
        return set(_bot_guild_cache)

    async with _bot_guild_lock:
        now = time.monotonic()
        if (
            not force
            and _bot_guild_cache_at
            and (now - _bot_guild_cache_at) < _BOT_GUILD_TTL
        ):
            return set(_bot_guild_cache)
        try:
            guilds = await discord_api(
                "GET",
                "/users/@me/guilds",
                token=DISCORD_TOKEN,
                token_type="Bot",
            )
            _bot_guild_cache = {str(g["id"]) for g in guilds}
            _bot_guild_cache_at = time.monotonic()
            return set(_bot_guild_cache)
        except Exception:
            # Prefer stale cache over empty list / hard failure.
            if _bot_guild_cache:
                return set(_bot_guild_cache)
            raise


async def fetch_guild_channels(guild_id: str) -> list[dict]:
    channels = await discord_api(
        "GET",
        f"/guilds/{guild_id}/channels",
        token=DISCORD_TOKEN,
        token_type="Bot",
    )
    text_like = []
    for ch in channels:
        # 0 guild text, 5 announcement
        if ch.get("type") in (0, 5):
            text_like.append(ch)
    text_like.sort(key=lambda c: (c.get("position", 0), c.get("name", "")))
    return text_like
