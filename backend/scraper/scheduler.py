import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from db.database import AsyncSessionLocal
from scraper.feed_fetcher import fetch_and_store_stories
from scraper.ranker import rank_stories

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def run_pipeline(niche: str = "f1"):
    logger.info(f"Pipeline started for niche: {niche}")
    async with AsyncSessionLocal() as db:
        fetched = await fetch_and_store_stories(db, niche)
        ranked = await rank_stories(db, niche)
    logger.info(f"Pipeline complete — fetched: {fetched}, ranked: {ranked}")


def start_scheduler(niche: str = "f1", interval_minutes: int = 30):
    scheduler.add_job(
        run_pipeline,
        trigger=IntervalTrigger(minutes=interval_minutes),
        args=[niche],
        id="scraper_pipeline",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Scheduler started — running every {interval_minutes} minutes")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
