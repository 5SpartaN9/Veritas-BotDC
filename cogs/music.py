from __future__ import annotations

import asyncio
import re

import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands

YOUTUBE_PATTERN = re.compile(
    r"(https?://)?(www\.)?"
    r"(youtube\.com/watch\?v=|youtu\.be/|music\.youtube\.com/watch\?v=)[\w-]+",
    re.IGNORECASE,
)
SPOTIFY_PATTERN = re.compile(
    r"https?://open\.spotify\.com/(track|album|playlist|episode)/[\w-]+",
    re.IGNORECASE,
)

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch1",
    "extract_flat": False,
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


class MusicPlayer:
    def __init__(self, voice_client: discord.VoiceClient) -> None:
        self.voice_client = voice_client
        self.queue: list[tuple[str, str]] = []
        self.current_title: str | None = None
        self._worker: asyncio.Task | None = None
        self._idle = asyncio.Event()
        self._idle.set()

    @property
    def is_busy(self) -> bool:
        return bool(
            self.current_title
            or self.queue
            or self.voice_client.is_playing()
            or self.voice_client.is_paused()
        )

    def start(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._playback_loop())

    async def _playback_loop(self) -> None:
        while True:
            if not self.queue:
                self.current_title = None
                self._idle.set()
                await asyncio.sleep(0.5)
                continue

            self._idle.clear()
            title, url = self.queue.pop(0)
            self.current_title = title

            source = discord.FFmpegOpusAudio(url, **FFMPEG_OPTIONS)
            self.voice_client.play(source)

            while self.voice_client.is_playing() or self.voice_client.is_paused():
                await asyncio.sleep(0.4)

            self.current_title = None

    async def enqueue(self, query: str) -> tuple[str, int]:
        info = await asyncio.to_thread(self._extract_info, query)
        title = info.get("title", "Unknown track")
        audio_url = info["url"]
        self.queue.append((title, audio_url))
        position = len(self.queue) + (1 if self.current_title else 0)
        self.start()
        return title, position

    def skip(self) -> str | None:
        skipped = self.current_title
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()
        return skipped

    def pause(self) -> bool:
        if self.voice_client.is_playing():
            self.voice_client.pause()
            return True
        return False

    def resume(self) -> bool:
        if self.voice_client.is_paused():
            self.voice_client.resume()
            return True
        return False

    def clear(self) -> None:
        self.queue.clear()
        self.current_title = None
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()

    def queue_titles(self) -> list[str]:
        return [title for title, _ in self.queue]

    @staticmethod
    def _extract_info(query: str) -> dict:
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
            if YOUTUBE_PATTERN.search(query) or SPOTIFY_PATTERN.search(query):
                info = ydl.extract_info(query, download=False)
            else:
                info = ydl.extract_info(f"ytsearch1:{query}", download=False)

            if info is None:
                raise RuntimeError("Track not found.")

            if "entries" in info:
                info = info["entries"][0]

            if not info.get("url"):
                raise RuntimeError("Could not get an audio stream.")

            return info


class MusicControlView(discord.ui.View):
    def __init__(self, cog: Music) -> None:
        super().__init__(timeout=None)
        self.cog = cog

    async def _guild_player(
        self, interaction: discord.Interaction
    ) -> MusicPlayer | None:
        if not interaction.guild:
            await interaction.response.send_message(
                "This only works in a server.",
                ephemeral=True,
            )
            return None
        return self.cog._get_player(interaction.guild)

    @discord.ui.button(
        label="Pause",
        style=discord.ButtonStyle.secondary,
        emoji="⏸️",
        custom_id="veritas:music:pause",
    )
    async def pause_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        player = await self._guild_player(interaction)
        if player is None:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Nothing is playing.",
                    ephemeral=True,
                )
            return
        if player.pause():
            await interaction.response.send_message("⏸️ Paused.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "Nothing to pause.",
                ephemeral=True,
            )

    @discord.ui.button(
        label="Resume",
        style=discord.ButtonStyle.success,
        emoji="▶️",
        custom_id="veritas:music:resume",
    )
    async def resume_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        player = await self._guild_player(interaction)
        if player is None:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Nothing is playing.",
                    ephemeral=True,
                )
            return
        if player.resume():
            await interaction.response.send_message("▶️ Resumed.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "Playback is not paused.",
                ephemeral=True,
            )

    @discord.ui.button(
        label="Skip",
        style=discord.ButtonStyle.primary,
        emoji="⏭️",
        custom_id="veritas:music:skip",
    )
    async def skip_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        player = await self._guild_player(interaction)
        if player is None:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Nothing is playing.",
                    ephemeral=True,
                )
            return
        skipped = player.skip()
        if skipped:
            await interaction.response.send_message(
                f"⏭️ Skipped: **{skipped}**",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "Nothing to skip.",
                ephemeral=True,
            )

    @discord.ui.button(
        label="Queue",
        style=discord.ButtonStyle.secondary,
        emoji="📜",
        custom_id="veritas:music:queue",
    )
    async def queue_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        player = await self._guild_player(interaction)
        if player is None or not player.is_busy:
            await interaction.response.send_message(
                "Queue is empty.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            self.cog._format_queue(player),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Stop",
        style=discord.ButtonStyle.danger,
        emoji="⏹️",
        custom_id="veritas:music:stop",
    )
    async def stop_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "This only works in a server.",
                ephemeral=True,
            )
            return
        await self.cog._stop_playback(interaction.guild)
        await interaction.response.send_message(
            "⏹️ Playback stopped.",
            ephemeral=True,
        )


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.players: dict[int, MusicPlayer] = {}

    def _get_player(self, guild: discord.Guild) -> MusicPlayer | None:
        if guild.voice_client is None:
            return None
        return self.players.get(guild.id)

    def _format_queue(self, player: MusicPlayer) -> str:
        lines = ["**Music queue**"]
        if player.current_title:
            state = "⏸️" if player.voice_client.is_paused() else "▶️"
            lines.append(f"{state} Now: **{player.current_title}**")
        titles = player.queue_titles()
        if not titles and not player.current_title:
            return "Queue is empty."
        for index, title in enumerate(titles, start=1):
            lines.append(f"{index}. {title}")
        return "\n".join(lines)

    async def _stop_playback(self, guild: discord.Guild) -> None:
        player = self.players.pop(guild.id, None)
        if player:
            player.clear()
        if guild.voice_client:
            await guild.voice_client.disconnect()

    def build_panel_embed(self, guild: discord.Guild | None) -> discord.Embed:
        player = self._get_player(guild) if guild else None
        now = player.current_title if player else None
        queued = player.queue_titles() if player else []
        voice = guild.voice_client.channel.mention if guild and guild.voice_client else "—"

        if player and player.voice_client.is_paused():
            status = "⏸️ Paused"
        elif player and player.voice_client.is_playing():
            status = "▶️ Playing"
        else:
            status = "⏹️ Idle"

        embed = discord.Embed(
            title="Veritas — music panel",
            description="Control playback with the buttons below or `/music`, `/skip`, `/queue`.",
            color=discord.Color.from_rgb(30, 96, 145),
        )
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Channel", value=voice, inline=True)
        embed.add_field(name="Now playing", value=now or "—", inline=False)
        embed.add_field(name="Queued", value=str(len(queued)), inline=True)
        embed.set_footer(text="Veritas • Discord panel")
        return embed

    @app_commands.command(
        name="music",
        description="Play music from YouTube/Spotify or search by name.",
    )
    @app_commands.describe(link="YouTube/Spotify link or track name")
    async def music(self, interaction: discord.Interaction, link: str) -> None:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message(
                "Join a voice channel first.",
                ephemeral=True,
            )
            return

        if not interaction.guild:
            await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True,
            )
            return

        channel = interaction.user.voice.channel
        await interaction.response.defer(thinking=True)

        try:
            voice = interaction.guild.voice_client
            if voice is None:
                voice = await channel.connect()
            elif voice.channel.id != channel.id:
                await voice.move_to(channel)

            player = self.players.get(interaction.guild.id)
            if player is None or player.voice_client != voice:
                player = MusicPlayer(voice)
                self.players[interaction.guild.id] = player

            title, position = await player.enqueue(link.strip())
            if position <= 1:
                await interaction.followup.send(f"▶️ Playing: **{title}**")
            else:
                await interaction.followup.send(
                    f"➕ Queued (#{position}): **{title}**",
                )
        except Exception as exc:
            await interaction.followup.send(f"Could not play music: `{exc}`")

    @app_commands.command(name="skip", description="Skip the current track.")
    async def skip(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True,
            )
            return

        player = self._get_player(interaction.guild)
        if player is None:
            await interaction.response.send_message(
                "Nothing is playing.",
                ephemeral=True,
            )
            return

        skipped = player.skip()
        if skipped:
            await interaction.response.send_message(f"⏭️ Skipped: **{skipped}**")
        else:
            await interaction.response.send_message(
                "Nothing to skip.",
                ephemeral=True,
            )

    @app_commands.command(name="queue", description="Show the music queue.")
    async def queue(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True,
            )
            return

        player = self._get_player(interaction.guild)
        if player is None or not player.is_busy:
            await interaction.response.send_message("Queue is empty.")
            return

        await interaction.response.send_message(self._format_queue(player))

    @app_commands.command(name="pause", description="Pause playback.")
    async def pause(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True,
            )
            return

        player = self._get_player(interaction.guild)
        if player is None or not player.pause():
            await interaction.response.send_message(
                "Nothing to pause.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message("⏸️ Paused.")

    @app_commands.command(name="resume", description="Resume playback.")
    async def resume(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True,
            )
            return

        player = self._get_player(interaction.guild)
        if player is None or not player.resume():
            await interaction.response.send_message(
                "Playback is not paused.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message("▶️ Resumed.")

    @app_commands.command(
        name="nowplaying",
        description="Show the track currently playing.",
    )
    async def nowplaying(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True,
            )
            return

        player = self._get_player(interaction.guild)
        if player is None or not player.current_title:
            await interaction.response.send_message("Nothing is playing.")
            return

        state = "⏸️" if player.voice_client.is_paused() else "▶️"
        await interaction.response.send_message(
            f"{state} Now playing: **{player.current_title}**"
        )

    @app_commands.command(
        name="stop",
        description="Stop music and disconnect the bot from voice.",
    )
    async def stop(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message(
                "This command only works in a server.",
                ephemeral=True,
            )
            return

        await self._stop_playback(interaction.guild)
        await interaction.response.send_message("⏹️ Playback stopped.")

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.id != self.bot.user.id:
            return
        if before.channel and after.channel is None:
            self.players.pop(member.guild.id, None)


async def setup(bot: commands.Bot) -> None:
    cog = Music(bot)
    await bot.add_cog(cog)
    bot.add_view(MusicControlView(cog))
