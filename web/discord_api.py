from __future__ import annotations

from typing import Any

import httpx

from web.config import API_BASE, DISCORD_TOKEN


async def discord_api(
    method: str,
    path: str,
    *,
    token: str,
    token_type: str = "Bearer",
    json: dict | None = None,
    data: dict | None = None,
    headers: dict | None = None,
) -> Any:
    hdrs = {
        "Authorization": f"{token_type} {token}",
        **(headers or {}),
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(
            method,
            f"{API_BASE}{path}",
            headers=hdrs,
            json=json,
            data=data,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Discord API {response.status_code}: {response.text[:300]}"
            )
        if response.status_code == 204:
            return None
        return response.json()


async def fetch_bot_guild_ids() -> set[str]:
    if not DISCORD_TOKEN:
        return set()
    guilds = await discord_api(
        "GET",
        "/users/@me/guilds",
        token=DISCORD_TOKEN,
        token_type="Bot",
    )
    return {str(g["id"]) for g in guilds}


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
