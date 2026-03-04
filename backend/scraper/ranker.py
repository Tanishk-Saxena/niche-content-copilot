import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Story

logger = logging.getLogger(__name__)


def load_niche_config(niche: str = "f1") -> dict:
    config_path = Path(__file__).parent.parent / "config" / "niches" / f"{niche}.json"
    with open(config_path) as f:
        return json.load(f)


def is_race_weekend(config: dict) -> bool:
    today = datetime.now(timezone.utc).date()
    for weekend in config.get("race_weekends_2026", []):
        start = datetime.strptime(weekend["start"], "%Y-%m-%d").date()
        end = datetime.strptime(weekend["end"], "%Y-%m-%d").date()
        if start <= today <= end:
            return True
    return False


def compute_relevance_score(story: Story, keywords: list[str], race_weekend: bool) -> float:
    text = " ".join(filter(None, [story.title, story.summary, story.full_text])).lower()

    # Keyword match density (0-7 points)
    matches = sum(
        len(re.findall(r"\b" + re.escape(kw.lower()) + r"\b", text))
        for kw in keywords
    )
    # Normalize: cap at 20 matches → 7 points
    keyword_score = min(matches / 20.0, 1.0) * 7.0

    # Recency decay (0-3 points)
    recency_score = 0.0
    if story.published_at:
        now = datetime.now(timezone.utc)
        age_hours = (now - story.published_at).total_seconds() / 3600
        if age_hours <= 1:
            recency_score = 3.0
        elif age_hours <= 6:
            recency_score = 3.0 * (1 - (age_hours - 1) / 5)
        else:
            # Decay further but never below 0
            recency_score = max(0.0, 1.5 * (1 - (age_hours - 6) / 42))

    score = keyword_score + recency_score

    # Race weekend boost: +1.5 points, max 10
    if race_weekend and config_race_weekend_boost_enabled(story.niche):
        score = min(score + 1.5, 10.0)

    return round(min(score, 10.0), 3)


def config_race_weekend_boost_enabled(niche: str) -> bool:
    try:
        config = load_niche_config(niche)
        return config.get("race_weekend_boost", False)
    except Exception:
        return False


async def rank_stories(db: AsyncSession, niche: str = "f1") -> int:
    config = load_niche_config(niche)
    keywords = config.get("keywords", [])
    race_weekend = is_race_weekend(config)

    if race_weekend:
        logger.info("Race weekend detected — boost active")

    result = await db.execute(
        select(Story).where(Story.niche == niche, Story.status == "new")
    )
    stories = result.scalars().all()

    for story in stories:
        story.relevance_score = compute_relevance_score(story, keywords, race_weekend)

    await db.commit()
    logger.info(f"Ranked {len(stories)} stories for niche '{niche}'")
    return len(stories)
