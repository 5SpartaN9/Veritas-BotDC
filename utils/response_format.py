from __future__ import annotations

import re
from dataclasses import dataclass, field

import discord

URL_PATTERN = re.compile(r"https?://[^\s<>\]]+")
# Matches markdown like **Verdict:** value
FIELD_PATTERN = re.compile(
    r"\*\*\s*(Verdict|Answer|Explanation|Confidence|Reasoning|Uncertainty|"
    r"Topic|Sources|Mode|Claim A|Claim B|Agreements|Differences|"
    r"Extracted claims|Fact|Opinion|Unproven)\s*:?\s*\*\*\s*:?\s*",
    re.IGNORECASE,
)

VERDICT_COLORS = {
    "TRUE": discord.Color.from_rgb(46, 125, 50),
    "FALSE": discord.Color.from_rgb(198, 40, 40),
    "PARTLY TRUE": discord.Color.from_rgb(245, 124, 0),
    "UNVERIFIED": discord.Color.from_rgb(117, 117, 117),
    "DEFAULT": discord.Color.from_rgb(30, 96, 145),
}


@dataclass
class ParsedResponse:
    raw: str
    brief: bool = False
    verdict: str | None = None
    answer: str | None = None
    confidence: str | None = None
    reasoning: str | None = None
    uncertainty: str | None = None
    sources_text: str | None = None
    extra_fields: dict[str, str] = field(default_factory=dict)
    source_links: list[tuple[str, str]] = field(default_factory=list)


def _clean(value: str) -> str:
    return value.strip().strip('"').strip()


def parse_ai_response(text: str) -> ParsedResponse:
    result = ParsedResponse(raw=text)
    if not text:
        return result

    # Detect brief subjective replies (no structured headings)
    if not FIELD_PATTERN.search(text) and "**Verdict:**" not in text and "**Answer:**" not in text:
        result.brief = True
        result.answer = text.strip()
        return result

    parts = FIELD_PATTERN.split(text)
    # parts: [preamble, field1, value1, field2, value2, ...]
    if len(parts) < 3:
        result.answer = text.strip()
        result.source_links = _extract_links(text)
        return result

    fields: dict[str, str] = {}
    for i in range(1, len(parts), 2):
        if i + 1 >= len(parts):
            break
        name = parts[i].strip().lower()
        value = _clean(parts[i + 1])
        # Trim next field leakage already handled by split
        fields[name] = value

    if fields.get("mode", "").upper().startswith("BRIEF"):
        result.brief = True

    result.verdict = fields.get("verdict")
    result.answer = fields.get("answer") or fields.get("explanation")
    result.confidence = fields.get("confidence")
    result.reasoning = fields.get("reasoning")
    result.uncertainty = fields.get("uncertainty")
    result.sources_text = fields.get("sources")

    for key in (
        "topic",
        "claim a",
        "claim b",
        "agreements",
        "differences",
        "extracted claims",
        "fact",
        "opinion",
        "unproven",
    ):
        if key in fields:
            result.extra_fields[key] = fields[key]

    link_source = result.sources_text or text
    result.source_links = _extract_named_links(link_source)
    if not result.source_links:
        result.source_links = _extract_links(link_source)

    return result


def _extract_links(text: str) -> list[tuple[str, str]]:
    links = URL_PATTERN.findall(text)
    out: list[tuple[str, str]] = []
    for i, url in enumerate(links[:5], start=1):
        clean = url.rstrip(").,;]>\"'")
        out.append((f"Source {i}", clean))
    return out


def _extract_named_links(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for line in text.splitlines():
        urls = URL_PATTERN.findall(line)
        if not urls:
            continue
        url = urls[0].rstrip(").,;]>\"'")
        label = URL_PATTERN.sub("", line)
        label = re.sub(r"^[\d\.\-\*\s]+", "", label)
        label = label.replace("—", "-").split(" - ")[0].strip(" -:|")
        label = re.sub(r"\[.*?\]", "", label).strip() or f"Source {len(out) + 1}"
        if len(label) > 80:
            label = label[:77] + "..."
        out.append((label, url))
        if len(out) >= 5:
            break
    return out


def _normalize_verdict(verdict: str | None) -> str | None:
    if not verdict:
        return None
    text = " ".join(verdict.strip().split())
    upper = text.upper()
    for key in ("PARTLY TRUE", "TRUE", "FALSE", "UNVERIFIED"):
        if key in upper:
            return key.title() if key != "PARTLY TRUE" else "Partly true"
    # Keep short custom verdicts readable
    if len(text) > 80:
        text = text[:77] + "…"
    return text


def _shorten(text: str | None, limit: int = 900) -> str | None:
    if not text:
        return None
    clean = " ".join(text.strip().split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1] + "…"


def verdict_color(verdict: str | None) -> discord.Color:
    if not verdict:
        return VERDICT_COLORS["DEFAULT"]
    upper = verdict.upper()
    for key, color in VERDICT_COLORS.items():
        if key != "DEFAULT" and key in upper:
            return color
    return VERDICT_COLORS["DEFAULT"]


def build_response_embed(
    parsed: ParsedResponse,
    *,
    title: str = "Veritas",
    cached: bool = False,
) -> discord.Embed:
    if parsed.brief:
        embed = discord.Embed(
            title=title,
            description=_shorten(parsed.answer or parsed.raw, 1800) or "",
            color=VERDICT_COLORS["DEFAULT"],
        )
        footer = "Quick reply"
        if cached:
            footer += " · cached"
        embed.set_footer(text=footer)
        return embed

    verdict = _normalize_verdict(parsed.verdict)
    color = verdict_color(verdict or parsed.verdict)
    embed = discord.Embed(title=title, color=color)

    if verdict:
        embed.description = f"**{verdict}**"
        if parsed.confidence:
            conf = _shorten(parsed.confidence, 120)
            embed.description += f"\nConfidence: {conf}"

    summary = _shorten(parsed.answer or parsed.reasoning, 1000)
    if summary:
        embed.add_field(name="Summary", value=summary, inline=False)

    # Avoid duplicating the same text under Reasoning
    if (
        parsed.reasoning
        and parsed.answer
        and parsed.reasoning.strip() != parsed.answer.strip()
    ):
        reasoning = _shorten(parsed.reasoning, 700)
        if reasoning:
            embed.add_field(name="Why", value=reasoning, inline=False)

    if parsed.uncertainty:
        uncertainty = _shorten(parsed.uncertainty, 500)
        if uncertainty:
            embed.add_field(
                name="Uncertainty",
                value=uncertainty,
                inline=False,
            )

    labels = {
        "topic": "Topic",
        "claim a": "Claim A",
        "claim b": "Claim B",
        "agreements": "Agreements",
        "differences": "Differences",
        "extracted claims": "Extracted claims",
        "fact": "Fact",
        "opinion": "Opinion",
        "unproven": "Unproven",
    }
    for key, label in labels.items():
        if key in parsed.extra_fields:
            value = _shorten(parsed.extra_fields[key], 700)
            if value:
                embed.add_field(name=label, value=value, inline=False)

    if parsed.source_links:
        lines = [f"• [{label}]({url})" for label, url in parsed.source_links[:4]]
        embed.add_field(name="Sources", value="\n".join(lines)[:1024], inline=False)
    elif parsed.sources_text:
        short = _shorten(parsed.sources_text, 350)
        if short:
            embed.add_field(name="Sources", value=short, inline=False)

    if not embed.fields and not embed.description and parsed.raw:
        embed.description = parsed.raw[:1800]

    footer_bits = ["Prefer official & scientific sources"]
    if cached:
        footer_bits.append("cached")
    embed.set_footer(text=" · ".join(footer_bits))
    return embed


class SourceButtons(discord.ui.View):
    def __init__(self, links: list[tuple[str, str]]) -> None:
        super().__init__(timeout=600)
        for label, url in links[:5]:
            self.add_item(
                discord.ui.Button(
                    label=label[:80],
                    style=discord.ButtonStyle.link,
                    url=url,
                )
            )


async def send_parsed_interaction(
    interaction: discord.Interaction,
    parsed: ParsedResponse,
    *,
    title: str = "Veritas",
    cached: bool = False,
) -> None:
    embed = build_response_embed(parsed, title=title, cached=cached)
    view = SourceButtons(parsed.source_links) if parsed.source_links else None
    await interaction.followup.send(embed=embed, view=view)


async def reply_parsed_message(
    message: discord.Message,
    parsed: ParsedResponse,
    *,
    title: str = "Veritas",
    cached: bool = False,
) -> discord.Message:
    embed = build_response_embed(parsed, title=title, cached=cached)
    view = SourceButtons(parsed.source_links) if parsed.source_links else None
    return await message.reply(embed=embed, view=view, mention_author=False)
