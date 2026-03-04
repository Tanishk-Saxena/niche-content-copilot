"""
Manual Phase 2 test — verifies Claude draft generation end-to-end.
Usage: python test_phase2.py [N]   (N = number of stories to test, default 3)
"""
import asyncio
import io
import json
import logging
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

N_STORIES = int(sys.argv[1]) if len(sys.argv) > 1 else 3


def _print_drafts(story, drafts):
    print("\n" + "=" * 60)
    print(f"[{story.relevance_score:.2f}] {story.title[:70]}")
    print(f"Source: {story.source}")
    print("=" * 60)
    for draft in drafts:
        fmt = draft["format"]
        content = draft["content"]
        print(f"\n--- {fmt.upper()} ---")
        if fmt == "text_post":
            text = content.get("text", "")
            print(text)
            print(f"[{len(text)} chars]")
        elif fmt == "thread":
            for i, tweet in enumerate(content.get("tweets", []), 1):
                print(f"{i}/ {tweet}")
                print(f"   [{len(tweet)} chars]")


async def generate_and_save(story, niche_config):
    from generation.claude_client import generate_all_drafts
    from db.database import AsyncSessionLocal
    from db.models import Draft, Story
    from sqlalchemy import select

    logger.info("Generating drafts for: %s", story.title[:70])
    drafts = await generate_all_drafts(story, niche_config)
    _print_drafts(story, drafts)

    async with AsyncSessionLocal() as db:
        for data in drafts:
            db.add(Draft(
                story_id=story.id,
                format=data["format"],
                content=data["content"],
                model=data["model"],
                prompt_version=data["prompt_version"],
                status="pending",
            ))
        result = await db.execute(select(Story).where(Story.id == story.id))
        s = result.scalar_one()
        s.status = "selected"
        await db.commit()

    return drafts


async def main():
    from db.database import AsyncSessionLocal
    from db.models import Story
    from sqlalchemy import select, desc

    # Pick top N stories spread across the ranked list
    logger.info("Fetching top %d stories from DB...", N_STORIES)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Story)
            .where(Story.niche == "f1")
            .order_by(desc(Story.relevance_score))
            .limit(N_STORIES)
        )
        stories = result.scalars().all()

    if not stories:
        logger.error("No stories in DB. Run test_phase1.py first.")
        sys.exit(1)

    logger.info("Found %d stories to test against.", len(stories))

    config_path = os.path.join(os.path.dirname(__file__), "config", "niches", "f1.json")
    with open(config_path, "r", encoding="utf-8") as f:
        niche_config = json.load(f)

    total_drafts = 0
    for story in stories:
        try:
            drafts = await generate_and_save(story, niche_config)
            total_drafts += len(drafts)
        except Exception as e:
            logger.error("Failed for story %s: %s", story.id, e)

    print(f"\n{'='*60}")
    print(f"Test complete. {len(stories)} stories, {total_drafts} drafts generated and saved.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
