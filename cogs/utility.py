from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from cogs.music import Music, MusicControlView
from config import PANEL_URL, SITE_URL
from utils.history import history_store
from utils.scores import score_store
from utils.settings import settings_store

ABOUT_DESCRIPTION = (
    "**Veritas** is an AI fact-checking bot for Discord.\n\n"
    "It verifies claims and answers questions using **official institutions** "
    "and **scientific sources** — not social media rumors or tabloids.\n\n"
    "If something can’t be confirmed, it says so instead of guessing.\n\n"
    f"🌐 Website: {SITE_URL}\n"
    f"⚙️ Control panel: {PANEL_URL}"
)

QUICK_START = (
    "1. `/ask question:` — ask anything factual\n"
    "2. `/check text:` — fact-check a claim\n"
    "3. **Reply** to a message with `@Veritas is that true?`\n"
    "4. Right-click a message → **Apps** → **Verify claim**\n"
    "5. `/help` — full command list"
)

ESSENTIAL_COMMANDS = (
    "`/about` `/help` — overview & full list\n"
    "`/ask` `/check` `/explain` `/sources`\n"
    "`/compare` `/cite` `/debate` `/multicheck`\n"
    "`/myscore` — your private fact-check stats\n"
    "`/settings` — language (admins)\n"
    "`/watchlist` — claim prompts on channel (admins)\n"
    "`/music` — play audio"
)

HELP_TEXT = """**Veritas — commands**

**Fact-check / knowledge**
• `/check text:` or `link:` — verify a statement
• `/ask question:` — answer from scientific/official sources
• `/sources topic:` — short list of credible sources
• `/explain topic:` — simple explanation + sources
• `/compare claim_a: claim_b:` — compare two versions
• `/cite text:` or `link:` — extract quotes/data and verify
• `/debate text:` — split into Fact / Opinion / Unproven
• `/multicheck text:` — check multiple claims (one per line)
• Right-click a message → **Verify claim**

**Chat**
• `@Veritas your question` — reply without a slash command
• Reply to a claim with `@Veritas is that true?` — checks that message

**Server**
• `/about` — bot overview (good to pin)
• `/help` — this list
• `/ping` — status and latency
• `/history count:` — recent checks on this channel
• `/myscore` — your TRUE/FALSE stats (private)
• `/settings language:` — Auto / EN / PL / RU / ZH (admins)
• `/panel` — music control panel
• `/autochat` — when the bot auto-replies
• `/watchlist` — offer Check this? on claim-like messages

**Music**
• `/music link:` — YouTube / Spotify / track name
• `/skip` `/queue` `/pause` `/resume` `/nowplaying` `/stop`

**Limits (budget plan)**
• Free: 2 AI requests per user / 10 minutes, 15 / day per server
• Premium: 8 AI requests per user / 10 minutes, 80 / day per server
• Repeated questions may use cache
"""


def build_about_embed(bot_user: discord.ClientUser | None = None) -> discord.Embed:
    embed = discord.Embed(
        title="Veritas — AI Fact-Checking Bot",
        description=ABOUT_DESCRIPTION,
        color=discord.Color.from_rgb(20, 24, 28),
    )
    embed.add_field(name="Quick start", value=QUICK_START, inline=False)
    embed.add_field(name="Essential commands", value=ESSENTIAL_COMMANDS, inline=False)
    embed.add_field(
        name="Tip",
        value=(
            "Reply to someone’s message with `@Veritas is that true?` — "
            "you don’t need to repeat their claim."
        ),
        inline=False,
    )
    embed.set_footer(text="Veritas • truth over noise • /help for everything")
    if bot_user:
        embed.set_thumbnail(url=bot_user.display_avatar.url)
    return embed


class Utility(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _music_cog(self) -> Music | None:
        return self.bot.get_cog("Music")  # type: ignore[return-value]

    @app_commands.command(
        name="about",
        description="What Veritas is and how to use the main commands.",
    )
    async def about(self, interaction: discord.Interaction) -> None:
        embed = build_about_embed(self.bot.user)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="help", description="List commands with usage examples.")
    async def help_command(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="Veritas — help",
            description=HELP_TEXT,
            color=discord.Color.from_rgb(30, 96, 145),
        )
        embed.add_field(
            name="Examples",
            value=(
                "`/ask question: Do vaccines cause autism?`\n"
                "`/check text: The Earth is flat`\n"
                "`/debate text: Social media is destroying democracy`\n"
                "`/multicheck text: 1) Claim A\\n2) Claim B`\n"
                "Reply → `@Veritas is that true?`"
            ),
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="myscore",
        description="Your private fact-check score (claims linked to you).",
    )
    async def myscore(self, interaction: discord.Interaction) -> None:
        stats = score_store.get(interaction.user.id)
        embed = discord.Embed(
            title="Your Veritas score",
            description=(
                "Counts verdicts from checks tied to you "
                "(your `/check` claims or messages verified about you)."
            ),
            color=discord.Color.from_rgb(30, 96, 145),
        )
        embed.add_field(name="TRUE", value=str(stats.get("true", 0)), inline=True)
        embed.add_field(name="FALSE", value=str(stats.get("false", 0)), inline=True)
        embed.add_field(name="PARTLY", value=str(stats.get("partly", 0)), inline=True)
        embed.add_field(
            name="UNVERIFIED",
            value=str(stats.get("unverified", 0)),
            inline=True,
        )
        embed.add_field(name="Total", value=str(stats.get("total", 0)), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="settings",
        description="Server settings for Veritas (admins).",
    )
    @app_commands.describe(language="Reply language for AI answers")
    @app_commands.choices(
        language=[
            app_commands.Choice(name="Auto (match user message)", value="auto"),
            app_commands.Choice(name="English", value="en"),
            app_commands.Choice(name="Polish", value="pl"),
            app_commands.Choice(name="Russian", value="ru"),
            app_commands.Choice(name="Chinese (Simplified)", value="zh"),
        ]
    )
    @app_commands.default_permissions(manage_guild=True)
    async def settings(
        self,
        interaction: discord.Interaction,
        language: app_commands.Choice[str],
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "Server only.",
                ephemeral=True,
            )
            return

        settings_store.set_language(interaction.guild.id, language.value)
        await interaction.response.send_message(
            f"✅ AI reply language set to **{language.name}**.",
        )

    @app_commands.command(name="ping", description="Bot status and latency.")
    async def ping(self, interaction: discord.Interaction) -> None:
        latency_ms = round(self.bot.latency * 1000)
        music = self._music_cog()
        voice_count = 0
        if music:
            voice_count = sum(
                1 for player in music.players.values() if player.voice_client.is_connected()
            )

        lang = settings_store.get_language(
            interaction.guild.id if interaction.guild else None
        )
        embed = discord.Embed(
            title="Veritas — status",
            color=discord.Color.from_rgb(46, 125, 50),
        )
        embed.add_field(name="Ping", value=f"{latency_ms} ms", inline=True)
        embed.add_field(name="Servers", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Voice links", value=str(voice_count), inline=True)
        embed.add_field(name="Language", value=lang, inline=True)
        embed.add_field(
            name="UTC time",
            value=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            inline=False,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="history",
        description="Recent fact-checks / AI queries on this channel.",
    )
    @app_commands.describe(count="How many entries to show (1–20)")
    async def history(
        self,
        interaction: discord.Interaction,
        count: app_commands.Range[int, 1, 20] = 10,
    ) -> None:
        if not interaction.channel:
            await interaction.response.send_message(
                "No channel.",
                ephemeral=True,
            )
            return

        entries = history_store.for_channel(interaction.channel.id, limit=count)
        if not entries:
            await interaction.response.send_message(
                "No history on this channel yet.",
                ephemeral=True,
            )
            return

        lines: list[str] = []
        for entry in entries:
            stamp = entry.timestamp.replace("T", " ").replace("+00:00", " UTC")
            lines.append(
                f"`{stamp}` **/{entry.command}** <@{entry.user_id}>\n"
                f"↳ {entry.preview}\n"
                f"→ {entry.summary}"
            )

        embed = discord.Embed(
            title=f"Channel history (last {len(entries)})",
            description="\n\n".join(lines)[:4000],
            color=discord.Color.from_rgb(30, 96, 145),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="panel",
        description="Post the bot control panel (music + shortcuts).",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def panel(self, interaction: discord.Interaction) -> None:
        music = self._music_cog()
        if music is None:
            await interaction.response.send_message(
                "Music module is not loaded.",
                ephemeral=True,
            )
            return

        embed = music.build_panel_embed(interaction.guild)
        embed.add_field(
            name="Quick commands",
            value=(
                "`/about` `/help` `/ask` `/check` `/debate` `/multicheck`\n"
                "`/myscore` `/settings` `/watchlist` `/history`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Web control panel",
            value=f"[Open dashboard]({PANEL_URL})",
            inline=False,
        )
        view = MusicControlView(music)
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Utility(bot))
