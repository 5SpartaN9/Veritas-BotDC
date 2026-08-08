import re

import discord
from discord import app_commands
from discord.ext import commands

from ai.gemini import (
    ask_question,
    cite_and_verify,
    compare_claims,
    debate_statement,
    explain_topic,
    list_sources,
    verify_claim,
    verify_multiple,
)
from utils.ai_pipeline import run_ai_interaction

MESSAGE_LINK_PATTERN = re.compile(
    r"https?://(?:ptb\.|canary\.)?discord(?:app)?\.com/channels/"
    r"(?P<guild_id>\d+|@me)/(?P<channel_id>\d+)/(?P<message_id>\d+)"
)


class AICommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _resolve_text(
        self,
        interaction: discord.Interaction,
        text: str | None,
        link: str | None,
    ) -> str | None:
        if text and text.strip():
            return text.strip()

        if not link or not link.strip():
            return None

        match = MESSAGE_LINK_PATTERN.match(link.strip())
        if not match:
            return None

        channel_id = int(match.group("channel_id"))
        message_id = int(match.group("message_id"))
        channel = interaction.client.get_channel(channel_id)
        if channel is None:
            channel = await interaction.client.fetch_channel(channel_id)

        if not isinstance(channel, discord.abc.Messageable):
            return None

        message = await channel.fetch_message(message_id)
        return message.content.strip() or None

    @app_commands.command(
        name="check",
        description="Fact-check a statement using official and scientific sources.",
    )
    @app_commands.describe(
        text="Text to verify",
        link="Optional: Discord message link",
    )
    async def check(
        self,
        interaction: discord.Interaction,
        text: str | None = None,
        link: str | None = None,
    ) -> None:
        claim = await self._resolve_text(interaction, text, link)
        if not claim:
            await interaction.response.send_message(
                "Provide **text** to check or a Discord message **link**.\n"
                "Tip: right-click a message → *Copy Message Link* → paste into `/check`.",
                ephemeral=True,
            )
            return

        await run_ai_interaction(
            interaction,
            command_name="check",
            label="fact-checking",
            preview=claim,
            runner=verify_claim,
            runner_kwargs={"claim": claim},
            score_user_id=interaction.user.id,
            title="Veritas — Fact check",
        )

    @app_commands.command(
        name="ask",
        description="Ask a question — answers based on scientific and official sources.",
    )
    @app_commands.describe(question="Your question")
    async def ask(self, interaction: discord.Interaction, question: str) -> None:
        if len(question.strip()) < 3:
            await interaction.response.send_message(
                "Question is too short.",
                ephemeral=True,
            )
            return

        q = question.strip()
        await run_ai_interaction(
            interaction,
            command_name="ask",
            label="answering",
            preview=q,
            runner=ask_question,
            runner_kwargs={"question": q},
            title="Veritas — Answer",
        )

    @app_commands.command(
        name="sources",
        description="Short list of credible sources for a topic.",
    )
    @app_commands.describe(topic="Topic to find sources for")
    async def sources(self, interaction: discord.Interaction, topic: str) -> None:
        if len(topic.strip()) < 3:
            await interaction.response.send_message(
                "Topic is too short.",
                ephemeral=True,
            )
            return

        t = topic.strip()
        await run_ai_interaction(
            interaction,
            command_name="sources",
            label="finding sources",
            preview=t,
            runner=list_sources,
            runner_kwargs={"topic": t},
            title="Veritas — Sources",
        )

    @app_commands.command(
        name="explain",
        description="Explain a concept simply + official/scientific sources.",
    )
    @app_commands.describe(topic="Concept or topic to explain")
    async def explain(self, interaction: discord.Interaction, topic: str) -> None:
        if len(topic.strip()) < 2:
            await interaction.response.send_message(
                "Provide a concept to explain.",
                ephemeral=True,
            )
            return

        t = topic.strip()
        await run_ai_interaction(
            interaction,
            command_name="explain",
            label="explaining",
            preview=t,
            runner=explain_topic,
            runner_kwargs={"topic": t},
            title="Veritas — Explain",
        )

    @app_commands.command(
        name="compare",
        description="Compare two claims or versions of an event.",
    )
    @app_commands.describe(
        claim_a="First claim / version",
        claim_b="Second claim / version",
    )
    async def compare(
        self,
        interaction: discord.Interaction,
        claim_a: str,
        claim_b: str,
    ) -> None:
        if len(claim_a.strip()) < 3 or len(claim_b.strip()) < 3:
            await interaction.response.send_message(
                "Both claims need meaningful text.",
                ephemeral=True,
            )
            return

        a = claim_a.strip()
        b = claim_b.strip()
        await run_ai_interaction(
            interaction,
            command_name="compare",
            label="comparing",
            preview=f"A: {a[:80]} | B: {b[:80]}",
            runner=compare_claims,
            runner_kwargs={"claim_a": a, "claim_b": b},
            title="Veritas — Compare",
        )

    @app_commands.command(
        name="cite",
        description="Extract quotes/data from text and check if they can be confirmed.",
    )
    @app_commands.describe(
        text="Text to analyze",
        link="Optional: Discord message link",
    )
    async def cite(
        self,
        interaction: discord.Interaction,
        text: str | None = None,
        link: str | None = None,
    ) -> None:
        body = await self._resolve_text(interaction, text, link)
        if not body:
            await interaction.response.send_message(
                "Provide **text** or a message **link** with quotes/data.",
                ephemeral=True,
            )
            return

        await run_ai_interaction(
            interaction,
            command_name="cite",
            label="analyzing citations",
            preview=body,
            runner=cite_and_verify,
            runner_kwargs={"text": body},
            title="Veritas — Cite",
        )

    @app_commands.command(
        name="debate",
        description="Split a statement into Fact / Opinion / Unproven.",
    )
    @app_commands.describe(
        text="Statement to break down",
        link="Optional: Discord message link",
    )
    async def debate(
        self,
        interaction: discord.Interaction,
        text: str | None = None,
        link: str | None = None,
    ) -> None:
        body = await self._resolve_text(interaction, text, link)
        if not body:
            await interaction.response.send_message(
                "Provide **text** or a message **link** to debate.",
                ephemeral=True,
            )
            return

        await run_ai_interaction(
            interaction,
            command_name="debate",
            label="debating",
            preview=body,
            runner=debate_statement,
            runner_kwargs={"text": body},
            title="Veritas — Debate",
        )

    @app_commands.command(
        name="multicheck",
        description="Fact-check multiple claims at once (one per line).",
    )
    @app_commands.describe(
        text="Claims separated by new lines, e.g. 1) ... 2) ...",
    )
    async def multicheck(self, interaction: discord.Interaction, text: str) -> None:
        body = text.strip()
        if len(body) < 5:
            await interaction.response.send_message(
                "Provide at least one claim (ideally several lines).",
                ephemeral=True,
            )
            return

        await run_ai_interaction(
            interaction,
            command_name="multicheck",
            label="multi-checking",
            preview=body,
            runner=verify_multiple,
            runner_kwargs={"text": body},
            score_user_id=interaction.user.id,
            title="Veritas — Multi-check",
        )


@app_commands.context_menu(name="Verify claim")
async def check_context_menu(
    interaction: discord.Interaction,
    message: discord.Message,
) -> None:
    claim = message.content.strip()
    if not claim:
        await interaction.response.send_message(
            "That message has no text to check.",
            ephemeral=True,
        )
        return

    await run_ai_interaction(
        interaction,
        command_name="check",
        label="fact-checking",
        preview=claim,
        runner=verify_claim,
        runner_kwargs={"claim": claim},
        score_user_id=message.author.id,
        title="Veritas — Fact check",
    )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AICommands(bot))
    bot.tree.add_command(check_context_menu)
