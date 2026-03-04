import logging
import os
from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db, init_db
from db.models import Story
from scraper.scheduler import run_pipeline, start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)

ACTIVE_NICHE = os.getenv("ACTIVE_NICHE", "f1")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_scheduler(niche=ACTIVE_NICHE, interval_minutes=30)
    yield
    stop_scheduler()


app = FastAPI(title="Niche Content Copilot API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Response schemas ---

class StoryResponse(BaseModel):
    id: UUID
    niche: str
    title: str
    url: str
    source: str
    summary: Optional[str]
    published_at: Optional[str]
    fetched_at: Optional[str]
    relevance_score: float
    status: str

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_model(cls, story: Story) -> "StoryResponse":
        return cls(
            id=story.id,
            niche=story.niche,
            title=story.title,
            url=story.url,
            source=story.source,
            summary=story.summary,
            published_at=story.published_at.isoformat() if story.published_at else None,
            fetched_at=story.fetched_at.isoformat() if story.fetched_at else None,
            relevance_score=story.relevance_score or 0,
            status=story.status,
        )


# --- Routes ---

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/stories", response_model=list[StoryResponse])
async def get_stories(
    limit: int = Query(default=20, ge=1, le=100),
    niche: str = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    target_niche = niche or ACTIVE_NICHE
    result = await db.execute(
        select(Story)
        .where(Story.niche == target_niche)
        .order_by(desc(Story.relevance_score))
        .limit(limit)
    )
    stories = result.scalars().all()
    return [StoryResponse.from_orm_model(s) for s in stories]


@app.get("/stories/{story_id}", response_model=StoryResponse)
async def get_story(story_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Story).where(Story.id == story_id))
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    return StoryResponse.from_orm_model(story)


@app.post("/scrape", status_code=202)
async def trigger_scrape(niche: str = Query(default=None)):
    """Manually trigger a scrape+rank pipeline run."""
    target_niche = niche or ACTIVE_NICHE
    import asyncio
    asyncio.create_task(run_pipeline(target_niche))
    return {"message": f"Scrape pipeline triggered for niche '{target_niche}'"}
