from __future__ import annotations

import re
import time

import discord
from discord import app_commands
from discord.ext import commands

from ai.gemini import ask_question, verify_claim
from utils.ai_pipeline import run_ai_interaction, run_ai_message
from utils.settings import settings_store

QUESTION_HINT = re.compile(
    r"(\?|"
    r"^(czy|jak|dlaczego|kiedy|gdzie|kto|co|ile|które|który|która|czym|"
    r"is|are|was|were|do|does|did|can|could|would|should|what|why|when|where|who|how|which)\b)",
    re.IGNORECASE,
)
VERIFY_HINT = re.compile(
    r"\b(sprawd[zź]|czy to prawda|zweryfikuj|fact[\s-]?check|verify|"
    r"is (that|this) true|check (this|that)|true\?|prawda\?)\b",
    re.IGNORECASE,
)
SHORT_FOLLOWUP = re.compile(
    r"^(czy to prawda\??|is (that|this) true\??|verify( this| that)?\??|"
    r"check( this| that)?\??|sprawd[zź]( to)?\??|zweryfikuj( to)?\??|"
    r"prawda\??|true\??|really\??|naprawdę\??|sure\??|ok\??)$",
    re.IGNORECASE,
)
WATCHLIST_HINT = re.compile(
    r"(\d+([.,]\d+)?\s*%|"
    r"\b(udowodniono|scientifically|proven|studies show|badania pokaz|fakt(em)? jest|"
    r"always|never|każdy|wszyscy|nobody|everyone)\b)",
    re.IGNORECASE,
)

MODE_CHOICES = [
    app_commands.Choice(name="Off", value="off"),
    app_commands.Choice(name="Mentions / replies to bot only", value="mention"),
    app_commands.Choice(name="Questions + mentions", value="questions"),
    app_commands.Choice(name="Almost all messages", value="all"),
]


class WatchCheckView(discord.ui.View):
    def __init__(self, claim: str, claim_author_id: int) -> None:
        super().__init__(timeout=600)
        self.claim = claim
        self.claim_author_id = claim_author_id

    @discord.ui.button(
        label="Check this?",
        style=discord.ButtonStyle.primary,
        emoji="🔍",
    )
    async def check_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer(thinking=True)
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if interaction.message:
            try:
                await interaction.message.edit(view=self)
            except discord.HTTPException:
                pass

        await run_ai_interaction(
            interaction,
            command_name="watchcheck",
            label="watchlist checking",
            preview=self.claim,
            runner=verify_claim,
            runner_kwargs={"claim": self.claim},
            score_user_id=self.claim_author_id,
            title="Veritas — Watchlist check",
            pre_deferred=True,
        )


class AutoChat(commands.Cog):
    """Automatic chat replies + watchlist prompts."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._cooldown: dict[int, float] = {}
        self._busy_channels: set[int] = set()
        self._watch_cooldown: dict[int, float] = {}

    def _strip_mention(self, message: discord.Message) -> str:
        content = message.content
        if self.bot.user:
            content = content.replace(f"<@{self.bot.user.id}>", "")
            content = content.replace(f"<@!{self.bot.user.id}>", "")
        return re.sub(r"\s+", " ", content).strip()

    def _is_question(self, text: str) -> bool:
        return bool(QUESTION_HINT.search(text.strip()))

    def _mentioned_or_reply_to_bot(self, message: discord.Message) -> bool:
        mentioned = self.bot.user is not None and self.bot.user.mentioned_in(message)
        reply_to_bot = (
            message.reference is not None
            and message.reference.resolved is not None
            and isinstance(message.reference.resolved, discord.Message)
            and self.bot.user is not None
            and message.reference.resolved.author.id == self.bot.user.id
        )
        return mentioned or reply_to_bot

    def _should_reply(self, message: discord.Message, mode: str, text: str) -> bool:
        if mode == "off":
            return False
        if self._mentioned_or_reply_to_bot(message):
            return True
        if mode == "mention":
            return False
        if mode == "questions":
            return self._is_question(text) and len(text) >= 5
        if mode == "all":
            return len(text) >= 5
        return False

    async def _referenced_message(
        self, message: discord.Message
    ) -> discord.Message | None:
        if not message.reference:
            return None

        resolved = message.reference.resolved
        if isinstance(resolved, discord.Message) and resolved.content.strip():
            return resolved

        msg_id = message.reference.message_id
        if msg_id is None:
            return None
        try:
            fetched = await message.channel.fetch_message(msg_id)
        except (discord.NotFound, discord.HTTPException):
            return None
        return fetched if fetched.content.strip() else None

    async def _resolve_user_text(
        self, message: discord.Message, text: str
    ) -> tuple[str, bool, int | None]:
        referenced = await self._referenced_message(message)

        if referenced and self.bot.user and referenced.author.id == self.bot.user.id:
            if not text:
                return (
                    "Continue the conversation from context. "
                    "If the user's last message is subjective — reply briefly.",
                    False,
                    None,
                )
            return (
                f"The user is replying to your previous message.\n"
                f"Your previous message:\n\"\"\"{referenced.content.strip()}\"\"\"\n\n"
                f"Their follow-up: {text}",
                False,
                None,
            )

        if referenced and (
            not text or SHORT_FOLLOWUP.match(text) or VERIFY_HINT.search(text)
        ):
            claim = referenced.content.strip()
            author = referenced.author.display_name
            return (
                f"Claim from {author} (id:{referenced.author.id}):\n\"\"\"{claim}\"\"\"\n\n"
                f"The user asked to verify this (follow-up: {text or 'is that true?'}).",
                True,
                referenced.author.id,
            )

        if referenced and text:
            verify = bool(VERIFY_HINT.search(text))
            return (
                f"The user is replying to this message from "
                f"{referenced.author.display_name} (id:{referenced.author.id}):\n"
                f"\"\"\"{referenced.content.strip()}\"\"\"\n\n"
                f"Their question: {text}",
                verify,
                referenced.author.id if verify else None,
            )

        if text:
            verify = bool(VERIFY_HINT.search(text))
            return text, verify, message.author.id if verify else None

        async for prev in message.channel.history(limit=8):
            if prev.id == message.id:
                continue
            if prev.author.bot:
                continue
            if not prev.content.strip():
                continue
            return (
                f"Claim from {prev.author.display_name} (id:{prev.author.id}):\n"
                f"\"\"\"{prev.content.strip()}\"\"\"\n\n"
                "The user mentioned you with no text — verify/answer that claim.",
                True,
                prev.author.id,
            )

        return (
            "The user mentioned you but asked nothing. "
            "Briefly ask for a concrete factual claim or question.",
            False,
            None,
        )

    def _cooldown_ok(self, channel_id: int, seconds: float = 4.0) -> bool:
        now = time.monotonic()
        last = self._cooldown.get(channel_id, 0.0)
        if now - last < seconds:
            return False
        self._cooldown[channel_id] = now
        return True

    def _watch_cooldown_ok(self, channel_id: int, seconds: float = 45.0) -> bool:
        now = time.monotonic()
        last = self._watch_cooldown.get(channel_id, 0.0)
        if now - last < seconds:
            return False
        self._watch_cooldown[channel_id] = now
        return True

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        if not message.content or message.content.startswith("/"):
            return

        if settings_store.get_watchlist(message.channel.id):
            from utils.plans import has_premium_features

            if not has_premium_features(message.guild.id):
                return
            if (
                WATCHLIST_HINT.search(message.content)
                and len(message.content) >= 20
                and not self._mentioned_or_reply_to_bot(message)
                and self._watch_cooldown_ok(message.channel.id)
            ):
                view = WatchCheckView(message.content.strip(), message.author.id)
                await message.reply(
                    "This looks like a factual claim. Want Veritas to check it?",
                    view=view,
                    mention_author=False,
                )

        mode = settings_store.get_autochat(message.channel.id)
        from utils.plans import autochat_mode_allowed

        if not autochat_mode_allowed(message.guild.id, mode):
            # Free servers: fall back to mention-only behavior
            mode = "mention"
        text = self._strip_mention(message)

        if not self._should_reply(message, mode, text):
            return
        if message.channel.id in self._busy_channels:
            return
        if not self._cooldown_ok(message.channel.id):
            return

        self._busy_channels.add(message.channel.id)
        try:
            prompt, force_verify, score_uid = await self._resolve_user_text(message, text)
            use_verify = force_verify or (
                mode == "all" and not self._is_question(prompt)
            )

            if use_verify:
                await run_ai_message(
                    message,
                    command_name="autocheck",
                    preview=prompt,
                    runner=verify_claim,
                    runner_kwargs={"claim": prompt},
                    score_user_id=score_uid,
                    title="Veritas — Fact check",
                )
            else:
                await run_ai_message(
                    message,
                    command_name="autochat",
                    preview=prompt,
                    runner=ask_question,
                    runner_kwargs={"question": prompt},
                    title="Veritas — Chat",
                )
        finally:
            self._busy_channels.discard(message.channel.id)

    @app_commands.command(
        name="autochat",
        description="Set when Veritas auto-replies in this channel.",
    )
    @app_commands.describe(mode="How aggressively the bot should reply")
    @app_commands.choices(mode=MODE_CHOICES)
    @app_commands.default_permissions(manage_channels=True)
    async def autochat(
        self,
        interaction: discord.Interaction,
        mode: app_commands.Choice[str],
    ) -> None:
        if not interaction.channel:
            await interaction.response.send_message("No channel.", ephemeral=True)
            return

        settings_store.set_autochat(interaction.channel.id, mode.value)
        from utils.plans import has_premium_features

        if mode.value in {"questions", "all"} and not has_premium_features(
            interaction.guild.id if interaction.guild else None
        ):
            settings_store.set_autochat(interaction.channel.id, "mention")
            await interaction.response.send_message(
                "Mode **Questions** / **Almost all** requires Premium or an active demo.\n"
                "Auto-chat kept at **Mentions** for this free server.",
                ephemeral=True,
            )
            return

        descriptions = {
            "off": "Bot will not auto-reply — slash commands only.",
            "mention": "Bot replies to `@Veritas` or replies to its messages.",
            "questions": "Same as above + auto-replies to questions (`?`).",
            "all": "Bot tries to reply to most messages (uses a lot of API quota).",
        }
        await interaction.response.send_message(
            f"✅ Auto-chat on this channel: **{mode.name}**\n{descriptions[mode.value]}",
        )

    @app_commands.command(
        name="watchlist",
        description="Toggle claim watchlist prompts on this channel (admins).",
    )
    @app_commands.describe(enabled="Turn watchlist on or off")
    @app_commands.default_permissions(manage_channels=True)
    async def watchlist(
        self,
        interaction: discord.Interaction,
        enabled: bool,
    ) -> None:
        if not interaction.channel:
            await interaction.response.send_message("No channel.", ephemeral=True)
            return

        settings_store.set_watchlist(interaction.channel.id, enabled)
        if enabled:
            from utils.plans import has_premium_features

            if not has_premium_features(interaction.guild.id if interaction.guild else None):
                settings_store.set_watchlist(interaction.channel.id, False)
                await interaction.response.send_message(
                    "Watchlist is a **Premium / demo** feature.\n"
                    "Open the dashboard to check your plan.",
                    ephemeral=True,
                )
                return
            await interaction.response.send_message(
                "✅ Watchlist **ON**. When messages look like factual claims, "
                "Veritas will offer a **Check this?** button (no auto API spend).",
            )
        else:
            await interaction.response.send_message("✅ Watchlist **OFF**.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoChat(bot))
