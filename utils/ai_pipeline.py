from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import discord

from utils.cache import response_cache
from utils.chat_context import fetch_channel_context
from utils.history import history_store
from utils.plans import command_allowed, get_plan_info, user_rate_limit
from utils.rate_limit import rate_limiter
from utils.response_format import (
    ParsedResponse,
    parse_ai_response,
    reply_parsed_message,
    send_parsed_interaction,
)
from utils.scores import score_store
from utils.settings import settings_store

AiCall = Callable[..., str]


def _first_line(text: str) -> str:
    for line in text.splitlines():
        cleaned = line.strip().lstrip("*").strip()
        if cleaned:
            return cleaned[:220]
    return text[:220]


async def _deny(
    interaction: discord.Interaction | None,
    message: discord.Message | None,
    text: str,
    *,
    pre_deferred: bool = False,
) -> None:
    if interaction is not None:
        if pre_deferred or interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)
    elif message is not None:
        await message.reply(text, mention_author=False)


async def run_ai_interaction(
    interaction: discord.Interaction,
    *,
    command_name: str,
    label: str,
    preview: str,
    runner: AiCall,
    runner_kwargs: dict[str, Any] | None = None,
    score_user_id: int | None = None,
    title: str = "Veritas",
    use_cache: bool = True,
    pre_deferred: bool = False,
) -> ParsedResponse | None:
    guild_id = interaction.guild.id if interaction.guild else None

    if not command_allowed(guild_id, command_name):
        await _deny(
            interaction,
            None,
            "This feature requires **Premium** or an active **3-month demo**.\n"
            "Open the dashboard to see your plan: http://127.0.0.1:8000/dashboard",
            pre_deferred=pre_deferred,
        )
        return None

    allowed, retry = rate_limiter.check(interaction.user.id, guild_id)
    if not allowed:
        limit = user_rate_limit(guild_id)
        if retry >= 86000:
            msg = (
                "Daily AI limit for this server reached.\n"
                "Check `/status` or upgrade in the dashboard for higher limits."
            )
        else:
            plan_label = get_plan_info(guild_id).label if guild_id else "Free"
            msg = (
                f"**{plan_label}** rate limit: max **{limit}** AI requests / 10 minutes.\n"
                f"Try again in **{retry}s** · `/status` for remaining quota."
            )
        await _deny(interaction, None, msg, pre_deferred=pre_deferred)
        return None

    if not pre_deferred and not interaction.response.is_done():
        await interaction.response.defer(thinking=True)
    runner_kwargs = dict(runner_kwargs or {})

    language = settings_store.get_language(guild_id)
    cache_key = response_cache.make_key(command_name, preview, language)
    cached_text = response_cache.get(cache_key) if use_cache else None
    cached = cached_text is not None

    try:
        if cached_text is None:
            context = None
            if interaction.channel:
                context = await fetch_channel_context(interaction.channel)

            who = interaction.user
            result = await asyncio.to_thread(
                runner,
                context=context,
                author=getattr(who, "display_name", who.name),
                author_id=who.id,
                language=language,
                **runner_kwargs,
            )
            if use_cache and not result.startswith(
                ("Gemini API quota", "Invalid Gemini", "Could not reach AI")
            ):
                response_cache.set(cache_key, result)
        else:
            result = cached_text

        parsed = parse_ai_response(result)
        await send_parsed_interaction(
            interaction,
            parsed,
            title=title,
            cached=cached,
        )

        if interaction.guild and interaction.channel:
            history_store.add(
                guild_id=interaction.guild.id,
                channel_id=interaction.channel.id,
                user_id=interaction.user.id,
                command=command_name,
                preview=preview,
                summary=_first_line(result),
            )

        if score_user_id and parsed.verdict:
            score_store.record(score_user_id, parsed.verdict)

        return parsed
    except Exception as exc:
        await interaction.followup.send(f"Error while {label}: `{exc}`")
        return None


async def run_ai_message(
    message: discord.Message,
    *,
    command_name: str,
    preview: str,
    runner: AiCall,
    runner_kwargs: dict[str, Any] | None = None,
    score_user_id: int | None = None,
    title: str = "Veritas",
    use_cache: bool = True,
) -> ParsedResponse | None:
    guild_id = message.guild.id if message.guild else None

    if not command_allowed(guild_id, command_name):
        await _deny(
            None,
            message,
            "This feature requires **Premium** or an active demo trial.",
        )
        return None

    allowed, retry = rate_limiter.check(message.author.id, guild_id)
    if not allowed:
        limit = user_rate_limit(guild_id)
        if retry >= 86000:
            msg = (
                "Daily AI limit for this server reached. "
                "Use `/status` or upgrade in the dashboard."
            )
        else:
            plan_label = get_plan_info(guild_id).label if guild_id else "Free"
            msg = (
                f"**{plan_label}** rate limit: max **{limit}** AI requests / 10 minutes.\n"
                f"Try again in **{retry}s** · `/status` for remaining quota."
            )
        await _deny(None, message, msg)
        return None

    runner_kwargs = dict(runner_kwargs or {})
    language = settings_store.get_language(guild_id)
    cache_key = response_cache.make_key(command_name, preview, language)
    cached_text = response_cache.get(cache_key) if use_cache else None
    cached = cached_text is not None

    async with message.channel.typing():
        try:
            if cached_text is None:
                context = await fetch_channel_context(
                    message.channel,
                    around=message,
                )
                result = await asyncio.to_thread(
                    runner,
                    context=context,
                    author=message.author.display_name,
                    author_id=message.author.id,
                    language=language,
                    **runner_kwargs,
                )
                if use_cache and not result.startswith(
                    ("Gemini API quota", "Invalid Gemini", "Could not reach AI")
                ):
                    response_cache.set(cache_key, result)
            else:
                result = cached_text

            parsed = parse_ai_response(result)
            await reply_parsed_message(
                message,
                parsed,
                title=title,
                cached=cached,
            )

            if message.guild:
                history_store.add(
                    guild_id=message.guild.id,
                    channel_id=message.channel.id,
                    user_id=message.author.id,
                    command=command_name,
                    preview=preview,
                    summary=_first_line(result),
                )

            if score_user_id and parsed.verdict:
                score_store.record(score_user_id, parsed.verdict)

            return parsed
        except Exception as exc:
            await message.reply(f"Could not reply: `{exc}`", mention_author=False)
            return None
