import discord


def split_message(text: str, limit: int = 2000) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""

    for line in text.split("\n"):
        candidate = f"{current}\n{line}".strip() if current else line
        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            chunks.append(current)
        while len(line) > limit:
            chunks.append(line[:limit])
            line = line[limit:]
        current = line

    if current:
        chunks.append(current)

    return chunks


async def send_long_message(
    interaction: discord.Interaction,
    content: str,
    *,
    ephemeral: bool = False,
) -> None:
    parts = split_message(content)
    await interaction.followup.send(parts[0], ephemeral=ephemeral)
    for part in parts[1:]:
        if interaction.channel:
            await interaction.channel.send(part)


async def reply_long_message(message: discord.Message, content: str) -> None:
    parts = split_message(content)
    await message.reply(parts[0], mention_author=False)
    for part in parts[1:]:
        await message.channel.send(part)
