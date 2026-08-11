import asyncio
import logging
import os

import discord
from discord.ext import commands

from config import DISCORD_TOKEN

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("veritas")

# Music (yt-dlp/voice) is heavy; keep it off on small hosts unless enabled.
ENABLE_MUSIC = os.getenv("VERITAS_ENABLE_MUSIC", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


class VeritasBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        # Do not enable members intent — it caches every user and blows RAM.

        super().__init__(
            command_prefix="!",
            intents=intents,
            description="Veritas — fact-checking and music bot for Discord.",
        )

    async def setup_hook(self) -> None:
        await self.load_extension("cogs.ai_commands")
        if ENABLE_MUSIC:
            await self.load_extension("cogs.music")
            logger.info("Music cog enabled")
        else:
            logger.info("Music cog disabled (set VERITAS_ENABLE_MUSIC=1 to enable)")
        await self.load_extension("cogs.utility")
        await self.load_extension("cogs.autochat")
        await self.tree.sync()
        logger.info("Commands synced with Discord.")

    async def on_ready(self) -> None:
        logger.info("Logged in as %s (ID: %s)", self.user, self.user.id)
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="@Veritas | /help",
            ),
        )

    async def on_guild_join(self, guild: discord.Guild) -> None:
        from utils.plans import ensure_early_trial

        info = ensure_early_trial(guild.id)
        logger.info(
            "Joined guild %s (%s) — plan=%s active=%s trial_ends=%s",
            guild.name,
            guild.id,
            info.plan,
            info.active,
            info.trial_ends,
        )


async def main() -> None:
    bot = VeritasBot()
    async with bot:
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped.")
