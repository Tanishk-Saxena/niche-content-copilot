import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import httpx
from newspaper import Article
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Story

logger = logging.getLogger(__name__)

NICHE_CONFIG_PATH = Path(__file__).parent.parent / "config" / "niches" / "f1.json"


def load_niche_config(niche: str = "f1") -> dict:
    config_path = Path(__file__).parent.parent / "config" / "niches" / f"{niche}.json"
    with open(config_path) as f:
        return json.load(f)


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def parse_feed_date(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                import time
                return datetime.fromtimestamp(time.mktime(parsed), tz=timezone.utc)
            except Exception:
                pass
    return None


async def fetch_full_text(url: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            html = resp.text

        article = Article(url)
        article.set_html(html)
        article.parse()
        return article.text if article.text else None
    except Exception as e:
        logger.warning(f"Failed to fetch full text for {url}: {e}")
        return None


async def fetch_and_store_stories(db: AsyncSession, niche: str = "f1") -> int:
    config = load_niche_config(niche)
    rss_sources = config.get("rss_sources", [])
    stored_count = 0

    for feed_url in rss_sources:
        try:
            logger.info(f"Fetching feed: {feed_url}")
            feed = feedparser.parse(feed_url)

            for entry in feed.entries[:20]:  # limit per feed to avoid hammering
                url = getattr(entry, "link", None)
                if not url:
                    continue

                # Deduplicate by URL
                existing = await db.execute(select(Story).where(Story.url == url))
                if existing.scalar_one_or_none():
                    continue

                title = getattr(entry, "title", "").strip()
                summary = getattr(entry, "summary", "").strip()
                source = feed.feed.get("title", feed_url)
                published_at = parse_feed_date(entry)

                # Fetch full article text
                full_text = await fetch_full_text(url)

                story = Story(
                    niche=niche,
                    title=title,
                    url=url,
                    source=source,
                    summary=summary[:1000] if summary else None,
                    full_text=full_text,
                    published_at=published_at,
                    status="new",
                )
                db.add(story)
                stored_count += 1
                logger.info(f"Stored: {title[:60]}")

        except Exception as e:
            logger.error(f"Error fetching feed {feed_url}: {e}")
            continue

    await db.commit()
    logger.info(f"Fetch complete. Stored {stored_count} new stories.")
    return stored_count
