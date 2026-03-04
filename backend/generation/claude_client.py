"""
Anthropic API wrapper for draft generation.
Generates text_post and thread variants for a given story.
"""

import asyncio
import json
import logging
import os
import re

from anthropic import AsyncAnthropic, APIError, APIStatusError

from generation.prompts import PROMPT_VERSION, build_system_prompt, build_user_message

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
MAX_TWEET_CHARS = 280

_client: AsyncAnthropic | None = None


def get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


# ---------------------------------------------------------------------------
# Core API call with retry
# ---------------------------------------------------------------------------

async def _call_claude(system: str, user: str, max_retries: int = 2) -> str:
    client = get_client()
    for attempt in range(max_retries + 1):
        try:
            response = await client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return response.content[0].text
        except APIStatusError as e:
            # Don't retry 4xx client errors (bad request, auth, etc.)
            if e.status_code < 500:
                raise
            if attempt < max_retries:
                wait = 2 ** attempt
                logger.warning("Claude API %s (attempt %d). Retrying in %ds", e.status_code, attempt + 1, wait)
                await asyncio.sleep(wait)
            else:
                raise
        except APIError as e:
            if attempt < max_retries:
                wait = 2 ** attempt
                logger.warning("Claude API error (attempt %d): %s. Retrying in %ds", attempt + 1, e, wait)
                await asyncio.sleep(wait)
            else:
                raise


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_text_post(raw: str) -> dict:
    text = raw.strip()

    # Strip JSON wrapping if the model returned {"text": "..."}
    if text.startswith("{"):
        try:
            parsed = json.loads(text)
            text = parsed.get("text", text)
        except json.JSONDecodeError:
            pass

    if len(text) > MAX_TWEET_CHARS:
        text = text[: MAX_TWEET_CHARS - 3] + "..."

    return {"type": "text_post", "text": text}


def _parse_thread(raw: str) -> dict:
    tweets: list[str] = []
    stripped = raw.strip()

    # Try JSON first: [{...}] or {"tweets": [...]}
    if stripped.startswith(("[", "{")):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                tweets = [str(t) for t in parsed]
            elif isinstance(parsed, dict):
                tweets = [str(t) for t in parsed.get("tweets", [])]
        except json.JSONDecodeError:
            pass

    if not tweets:
        # Split on numbered tweet markers: "1/", "2.", "Tweet 1:", etc.
        parts = re.split(r"\n(?=\d+[/.):]\s)", stripped)
        for part in parts:
            cleaned = re.sub(r"^\d+[/.):]\s*", "", part).strip()
            if cleaned:
                tweets.append(cleaned)

    # Truncate each tweet to 280 chars
    tweets = [t[: MAX_TWEET_CHARS - 3] + "..." if len(t) > MAX_TWEET_CHARS else t for t in tweets]

    return {"type": "thread", "tweets": tweets}


_PARSERS = {
    "text_post": _parse_text_post,
    "thread": _parse_thread,
    "caption": _parse_text_post,  # same shape as text_post
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_draft(story, fmt: str, niche_config: dict) -> dict:
    """
    Generate a single draft for the given story and format.
    Returns a dict ready to be merged into a Draft DB row.
    """
    system = build_system_prompt(niche_config)
    user = build_user_message(story, fmt)

    raw = await _call_claude(system, user)
    logger.info("Generated %s draft for story %s (%d chars raw)", fmt, story.id, len(raw))

    parser = _PARSERS.get(fmt, _parse_text_post)
    content = parser(raw)

    return {
        "format": fmt,
        "content": content,
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
    }


async def generate_all_drafts(story, niche_config: dict) -> list[dict]:
    """
    Generate both a text_post and a thread draft concurrently.
    Returns a list of two draft dicts.
    """
    text_post, thread = await asyncio.gather(
        generate_draft(story, "text_post", niche_config),
        generate_draft(story, "thread", niche_config),
    )
    return [text_post, thread]
