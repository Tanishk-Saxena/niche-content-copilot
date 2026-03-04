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

from generation.image_fetcher import fetch_og_image
from generation.prompts import PROMPT_VERSION, build_system_prompt, build_user_message

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
MAX_TWEET_CHARS = 280
# Twitter shortens all URLs to ~23 chars; reserve that space when a link is included
TWITTER_URL_CHARS = 23
MAX_TEXT_WITH_LINK = MAX_TWEET_CHARS - TWITTER_URL_CHARS - 1  # -1 for the space

_client: AsyncAnthropic | None = None


# ---------------------------------------------------------------------------
# Story type classifier
# ---------------------------------------------------------------------------

# These keywords in the title suggest the post is an opinion or analysis piece.
# Everything else is treated as news and gets a link + og:image.
_OPINION_TITLE_KEYWORDS = {
    "analysis", "opinion", "verdict", "review", "column", "comment",
    "could", "should", "must", "needs to", "the case for", "the case against",
    "explaining", "explained", "why ", "how ", "what if",
}
_HISTORICAL_TITLE_KEYWORDS = {
    "history", "greatest", "best ever", "remembered", "anniversary",
    "back in ", "years ago", "all-time", "classic", "legend",
}


def classify_story(story) -> str:
    """
    Returns 'news', 'analysis', or 'opinion'.
    - news      → include link + og:image in draft
    - analysis  → include link, no image
    - opinion   → no link, no image
    """
    text = (story.title or "").lower()
    for kw in _OPINION_TITLE_KEYWORDS:
        if kw in text:
            return "opinion"
    for kw in _HISTORICAL_TITLE_KEYWORDS:
        if kw in text:
            return "historical"
    return "news"


# ---------------------------------------------------------------------------
# Anthropic client
# ---------------------------------------------------------------------------

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

def _parse_text_post(raw: str, reserve_url_space: bool = False) -> dict:
    text = raw.strip()

    if text.startswith("{"):
        try:
            parsed = json.loads(text)
            text = parsed.get("text", text)
        except json.JSONDecodeError:
            pass

    limit = MAX_TEXT_WITH_LINK if reserve_url_space else MAX_TWEET_CHARS
    if len(text) > limit:
        text = text[:limit - 3] + "..."

    return {"type": "text_post", "text": text}


def _parse_thread(raw: str, reserve_url_space: bool = False) -> dict:
    tweets: list[str] = []
    stripped = raw.strip()

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
        parts = re.split(r"\n(?=\d+[/.):]\s)", stripped)
        for part in parts:
            cleaned = re.sub(r"^\d+[/.):]\s*", "", part).strip()
            if cleaned:
                tweets.append(cleaned)

    # First tweet gets the URL, so reserve space there only
    result = []
    for i, tweet in enumerate(tweets):
        limit = MAX_TEXT_WITH_LINK if (reserve_url_space and i == 0) else MAX_TWEET_CHARS
        result.append(tweet[:limit - 3] + "..." if len(tweet) > limit else tweet)

    return {"type": "thread", "tweets": result}


# ---------------------------------------------------------------------------
# Link + image enrichment
# ---------------------------------------------------------------------------

async def _enrich_content(content: dict, story, story_type: str) -> dict:
    """
    Adds 'link' and 'image_url' to the content dict based on story type.
    - news     → link + og:image
    - analysis → link only
    - opinion/historical → nothing added
    """
    if story_type in ("opinion", "historical"):
        return content

    content["link"] = story.url

    if story_type == "news":
        image_url = await fetch_og_image(story.url)
        if image_url:
            content["image_url"] = image_url
            logger.info("og:image found for story %s", story.id)
        else:
            logger.info("No og:image found for story %s", story.id)

    return content


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_draft(story, fmt: str, niche_config: dict, story_type: str = "news") -> dict:
    """
    Generate a single draft for the given story and format.
    Returns a dict ready to be merged into a Draft DB row.
    """
    system = build_system_prompt(niche_config)
    include_link = story_type in ("news", "analysis")
    user = build_user_message(story, fmt, include_link=include_link)

    raw = await _call_claude(system, user)
    logger.info("Generated %s draft for story %s (%d chars raw)", fmt, story.id, len(raw))

    if fmt == "text_post":
        content = _parse_text_post(raw, reserve_url_space=include_link)
    elif fmt == "thread":
        content = _parse_thread(raw, reserve_url_space=include_link)
    else:
        content = _parse_text_post(raw, reserve_url_space=include_link)

    content = await _enrich_content(content, story, story_type)

    return {
        "format": fmt,
        "content": content,
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "story_type": story_type,
    }


async def generate_all_drafts(story, niche_config: dict) -> list[dict]:
    """
    Classify the story, then generate text_post and thread drafts concurrently.
    Returns a list of two draft dicts.
    """
    story_type = classify_story(story)
    logger.info("Story classified as '%s': %s", story_type, story.title[:60])

    text_post, thread = await asyncio.gather(
        generate_draft(story, "text_post", niche_config, story_type),
        generate_draft(story, "thread", niche_config, story_type),
    )
    return [text_post, thread]
