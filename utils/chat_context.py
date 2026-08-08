from __future__ import annotations

import discord

MAX_CONTEXT_MESSAGES = 25
MAX_CONTEXT_CHARS = 3500


async def fetch_channel_context(
    channel: discord.abc.Messageable,
    *,
    around: discord.Message | None = None,
    limit: int = MAX_CONTEXT_MESSAGES,
) -> str:
    """Pobiera ostatnie wiadomości z etykietami użytkowników."""
    lines: list[str] = []

    history = channel.history(limit=limit, oldest_first=False)
    messages = [msg async for msg in history]
    messages.reverse()

    for msg in messages:
        if around and msg.id == around.id:
            continue
        if not msg.content:
            continue

        author = msg.author
        display = author.display_name if hasattr(author, "display_name") else author.name
        tag = "BOT" if author.bot else "USER"
        stamp = msg.created_at.strftime("%H:%M")
        content = msg.content.replace("\n", " ").strip()
        if len(content) > 400:
            content = content[:400] + "…"
        lines.append(f"[{stamp}] ({tag}) {display} (id:{author.id}): {content}")

    text = "\n".join(lines)
    if len(text) > MAX_CONTEXT_CHARS:
        text = text[-MAX_CONTEXT_CHARS:]
        cut = text.find("\n")
        if cut != -1:
            text = text[cut + 1 :]
    return text
