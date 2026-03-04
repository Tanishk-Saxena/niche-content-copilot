"""
Manual Phase 2 test — verifies Claude draft generation end-to-end.
Usage: python test_phase2.py
"""
import asyncio
import json
import logging
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
logger = logging.getLogger(__name__)


async def main():
    from db.database import AsyncSessionLocal
    from db.models import Story
    from sqlalchemy import select, desc

    # 1. Pick the top story from DB
    logger.info("Fetching top story from DB...")
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Story).order_by(desc(Story.relevance_score)).limit(1)
        )
        story = result.scalar_one_or_none()

    if not story:
        logger.error("No stories in DB. Run test_phase1.py first.")
        sys.exit(1)

    logger.info("Using story: [%.2f] %s", story.relevance_score, story.title[:80])
    logger.info("Source: %s | Has full_text: %s", story.source, bool(story.full_text))

    # 2. Load niche config
    import os
    config_path = os.path.join(os.path.dirname(__file__), "config", "niches", "f1.json")
    with open(config_path, "r", encoding="utf-8") as f:
        niche_config = json.load(f)

    # 3. Generate both draft variants
    from generation.claude_client import generate_all_drafts
    logger.info("Calling Claude API — generating text_post + thread...")
    drafts = await generate_all_drafts(story, niche_config)

    # 4. Print results
    print("\n" + "=" * 60)
    print(f"STORY: {story.title[:70]}")
    print("=" * 60)

    for draft in drafts:
        fmt = draft["format"]
        content = draft["content"]
        print(f"\n--- {fmt.upper()} (model: {draft['model']}, prompt v{draft['prompt_version']}) ---")
        if fmt == "text_post":
            text = content.get("text", "")
            print(f"{text}")
            print(f"[{len(text)} chars]")
        elif fmt == "thread":
            tweets = content.get("tweets", [])
            for i, tweet in enumerate(tweets, 1):
                print(f"{i}/ {tweet}")
                print(f"   [{len(tweet)} chars]")

    # 5. Persist to DB
    logger.info("Saving drafts to DB...")
    from db.models import Draft
    async with AsyncSessionLocal() as db:
        for data in drafts:
            draft_row = Draft(
                story_id=story.id,
                format=data["format"],
                content=data["content"],
                model=data["model"],
                prompt_version=data["prompt_version"],
                status="pending",
            )
            db.add(draft_row)
        story_result = await db.execute(select(Story).where(Story.id == story.id))
        s = story_result.scalar_one()
        s.status = "selected"
        await db.commit()

    logger.info("Drafts saved successfully.")

    # 6. Verify from DB
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Draft).where(Draft.story_id == story.id)
        )
        saved = result.scalars().all()

    print(f"\n{'='*60}")
    print(f"Phase 2 test complete. {len(saved)} draft(s) in DB for this story.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
