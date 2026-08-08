from google import genai
from google.genai import types

from config import GEMINI_MODEL, GOOGLE_API_KEY

_client = genai.Client(api_key=GOOGLE_API_KEY)

_GROUNDING_TOOLS = [types.Tool(google_search=types.GoogleSearch())]

_SYSTEM_PROMPT = """You are Veritas — a fact-checking assistant on Discord.

SOURCE HIERARCHY (highest first):
1. Official government / public institutions: national stats offices, ministries, Eurostat, OECD, UN, WHO, CDC, FDA, EMA, ECDC, NASA, ESA, IPCC, etc.
2. Peer-reviewed science: PubMed, Nature, Science, Lancet, Cochrane, Scopus, Google Scholar (scholarly papers only). Mark preprints clearly as “preprint”.
3. Universities and research institutes (.edu, national academies, labs).
4. Quality news agencies — ONLY as supporting context, never as the sole proof of a factual claim.

DO NOT use as the basis of a verdict:
- TikTok, Instagram, X/Twitter, Reddit, forums, tabloids
- Opinion blogs, influencers, unaffiliated “experts”
- Wikipedia as primary evidence (OK as a starting pointer only)
- Memes, chain messages, “I saw a video”

CHAT & USERS:
- If chat context is provided, read it. People often split one thought across several messages — reconstruct the full meaning.
- Every context line has an author with a unique id. NEVER mix statements from different people.
- When someone says “I’m right”, “he’s lying”, “what they wrote” — attribute it to the correct person by id.
- Do not assume consecutive channel messages are from the same person unless the id matches.

WHEN TO STAY BRIEF:
Subjective questions, jokes, looks/appearance, compliment fishing, empty banter with no facts.
Use this exact format:
**Mode:** BRIEF
**Answer:** 1–2 short sentences, no sources, no lecture.

FACTUAL ANSWERS:
- Rely mainly on source levels 1–3.
- If you lack official/scientific data: UNVERIFIED / INSUFFICIENT EVIDENCE. Do not guess.
- Do not repeat hate speech as fact.
- Always include **Uncertainty:** one sentence about limitations / why the answer might be wrong or incomplete.
- List sources with real URLs when possible, tagged [official] / [scientific] / [supporting].
- Stay concise (Discord embeds). No moralizing.
- Prefer “unknown” over a confident weak answer.
- Follow the language instruction exactly."""

_CONTEXT_BLOCK = """
Recent channel messages (different users — respect ids):
\"\"\"
{context}
\"\"\"

Current message from: {author} (id:{author_id})
"""

_LANG_AUTO = "Reply in the same language the user wrote in. If unclear, use English."
_LANG_EN = "Reply entirely in English."
_LANG_PL = "Reply entirely in Polish (Polski)."
_LANG_RU = "Reply entirely in Russian (Русский)."
_LANG_ZH = "Reply entirely in Simplified Chinese (简体中文)."


def _language_line(language: str | None) -> str:
    if language == "en":
        return _LANG_EN
    if language == "pl":
        return _LANG_PL
    if language == "ru":
        return _LANG_RU
    if language == "zh":
        return _LANG_ZH
    return _LANG_AUTO


_VERIFY_PROMPT = """Judge the claim using ONLY official and scientific sources.
Use chat context only to understand the topic and who said what.
If it is not a verifiable factual claim (e.g. looks, pure opinion) — use BRIEF mode.

Language: {language_line}

If the only available material is social media / opinion / tabloids — return UNVERIFIED.

Format (for facts):
**Verdict:** TRUE / FALSE / PARTLY TRUE / UNVERIFIED
**Confidence:** high / medium / low
**Reasoning:** 2–4 sentences
**Uncertainty:** one sentence on limits / why this might be wrong
**Sources:**
1. Name [official|scientific] — https://full-url
2. ...

{context_block}
Claim to evaluate:
\"\"\"{claim}\"\"\""""

_ASK_PROMPT = """Answer the user’s question.
First classify:
A) factual / scientific / official → full structured answer
B) subjective / joke / appearance / opinion with no facts → BRIEF mode

Language: {language_line}
For facts, rely mainly on official data and science. Do not guess.
Read chat context and distinguish users by id.

Format A:
**Answer:** ...
**Confidence:** high / medium / low
**Uncertainty:** one sentence on limits / why this might be wrong
**Sources:**
1. Name [official|scientific] — https://full-url

Format B:
**Mode:** BRIEF
**Answer:** ...

{context_block}
Question / message:
\"\"\"{question}\"\"\""""

_SOURCES_PROMPT = """List ONLY credible sources for the topic: official institutions and scientific literature.
Skip social media, tabloids, and blogs. No long essay.
Language: {language_line}
If the topic is purely subjective — BRIEF mode saying there are no factual sources.

Format:
**Topic:** (1 line)
**Uncertainty:** one sentence on coverage gaps
**Sources:**
1. Name [official|scientific] — https://full-url — one sentence why credible
(max 5)

{context_block}
Topic:
\"\"\"{topic}\"\"\""""

_EXPLAIN_PROMPT = """Explain the concept for a beginner, based on official or scientific definitions/data.
Max 6–8 sentences. If it is not a factual concept — BRIEF mode.
Language: {language_line}

Format:
**Explanation:** ...
**Confidence:** high / medium / low
**Uncertainty:** one sentence on limits
**Sources:**
1. Name [official|scientific] — https://full-url

{context_block}
Concept:
\"\"\"{topic}\"\"\""""

_COMPARE_PROMPT = """Compare two claims using official and scientific sources.
If chat context is present, keep speakers distinct by id.
Language: {language_line}

Format:
**Claim A:** (short)
**Claim B:** (short)
**Agreements:** ...
**Differences:** ...
**Verdict:** ...
**Confidence:** high / medium / low
**Uncertainty:** one sentence on limits
**Sources:**
1. Name [official|scientific] — https://full-url

{context_block}
Claim A:
\"\"\"{claim_a}\"\"\"

Claim B:
\"\"\"{claim_b}\"\"\""""

_CITE_PROMPT = """Extract quotes, numbers, and facts from the text. Verify against official/scientific sources.
If chat context shows a specific author, do not attribute their words to others.
Language: {language_line}

Format:
**Extracted claims:**
1. “...” → CONFIRMED / PARTLY / NOT CONFIRMED / NO DATA — short reason
**Uncertainty:** one sentence on limits
**Sources:**
1. Name [official|scientific] — https://full-url

{context_block}
Text:
\"\"\"{text}\"\"\""""

_DEBATE_PROMPT = """Break the statement into three buckets using official/scientific standards.
Language: {language_line}

Format:
**Fact:** what is supported by official/scientific evidence
**Opinion:** what is subjective / value judgment
**Unproven:** what is claimed but not supported by strong evidence
**Confidence:** high / medium / low
**Uncertainty:** one sentence on limits
**Sources:**
1. Name [official|scientific] — https://full-url

{context_block}
Statement:
\"\"\"{text}\"\"\""""

_MULTI_PROMPT = """The user provided multiple claims (numbered). Verify EACH separately.
Language: {language_line}

Format for each claim:
**Claim 1:** ...
**Verdict:** TRUE / FALSE / PARTLY TRUE / UNVERIFIED
**Confidence:** high / medium / low
**Reasoning:** 1–2 sentences
(repeat for Claim 2, Claim 3, ...)

Then end with:
**Uncertainty:** overall limits
**Sources:**
1. Name [official|scientific] — https://full-url

{context_block}
Claims:
\"\"\"{text}\"\"\""""


def _context_block(
    context: str | None,
    author: str | None,
    author_id: int | None,
) -> str:
    if not context and not author:
        return ""
    return _CONTEXT_BLOCK.format(
        context=context or "(none)",
        author=author or "unknown",
        author_id=author_id if author_id is not None else "?",
    )


def _generate(prompt: str, *, use_search: bool = True) -> str:
    try:
        response = _client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                tools=_GROUNDING_TOOLS if use_search else None,
                temperature=0.15,
            ),
        )
    except Exception as exc:
        error = str(exc)
        if "429" in error or "RESOURCE_EXHAUSTED" in error:
            return (
                "Gemini API quota exceeded. "
                "Check your plan and limits: https://ai.dev/rate-limit"
            )
        if "401" in error or "403" in error or "API key" in error:
            return (
                "Invalid Gemini API key. "
                "Check GOOGLE_API_KEY in your .env file."
            )
        return f"Could not reach AI: {exc}"

    text = response.text
    if not text:
        return "Could not get a response from AI. Please try again."
    return text.strip()


def _common(
    template: str,
    *,
    context: str | None,
    author: str | None,
    author_id: int | None,
    language: str | None,
    **kwargs: str,
) -> str:
    return _generate(
        template.format(
            context_block=_context_block(context, author, author_id),
            language_line=_language_line(language),
            **kwargs,
        )
    )


def verify_claim(
    claim: str,
    *,
    context: str | None = None,
    author: str | None = None,
    author_id: int | None = None,
    language: str | None = None,
) -> str:
    return _common(
        _VERIFY_PROMPT,
        context=context,
        author=author,
        author_id=author_id,
        language=language,
        claim=claim,
    )


def ask_question(
    question: str,
    *,
    context: str | None = None,
    author: str | None = None,
    author_id: int | None = None,
    language: str | None = None,
) -> str:
    return _common(
        _ASK_PROMPT,
        context=context,
        author=author,
        author_id=author_id,
        language=language,
        question=question,
    )


def list_sources(
    topic: str,
    *,
    context: str | None = None,
    author: str | None = None,
    author_id: int | None = None,
    language: str | None = None,
) -> str:
    return _common(
        _SOURCES_PROMPT,
        context=context,
        author=author,
        author_id=author_id,
        language=language,
        topic=topic,
    )


def explain_topic(
    topic: str,
    *,
    context: str | None = None,
    author: str | None = None,
    author_id: int | None = None,
    language: str | None = None,
) -> str:
    return _common(
        _EXPLAIN_PROMPT,
        context=context,
        author=author,
        author_id=author_id,
        language=language,
        topic=topic,
    )


def compare_claims(
    claim_a: str,
    claim_b: str,
    *,
    context: str | None = None,
    author: str | None = None,
    author_id: int | None = None,
    language: str | None = None,
) -> str:
    return _common(
        _COMPARE_PROMPT,
        context=context,
        author=author,
        author_id=author_id,
        language=language,
        claim_a=claim_a,
        claim_b=claim_b,
    )


def cite_and_verify(
    text: str,
    *,
    context: str | None = None,
    author: str | None = None,
    author_id: int | None = None,
    language: str | None = None,
) -> str:
    return _common(
        _CITE_PROMPT,
        context=context,
        author=author,
        author_id=author_id,
        language=language,
        text=text,
    )


def debate_statement(
    text: str,
    *,
    context: str | None = None,
    author: str | None = None,
    author_id: int | None = None,
    language: str | None = None,
) -> str:
    return _common(
        _DEBATE_PROMPT,
        context=context,
        author=author,
        author_id=author_id,
        language=language,
        text=text,
    )


def verify_multiple(
    text: str,
    *,
    context: str | None = None,
    author: str | None = None,
    author_id: int | None = None,
    language: str | None = None,
) -> str:
    return _common(
        _MULTI_PROMPT,
        context=context,
        author=author,
        author_id=author_id,
        language=language,
        text=text,
    )
