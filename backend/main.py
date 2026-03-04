import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db, init_db
from db.models import Draft, Story
from scraper.scheduler import run_pipeline, start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)

ACTIVE_NICHE = os.getenv("ACTIVE_NICHE", "f1")


def _load_niche_config(niche: str) -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "config", "niches", f"{niche}.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_scheduler(niche=ACTIVE_NICHE, interval_minutes=30)
    yield
    stop_scheduler()


app = FastAPI(title="Niche Content Copilot API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

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


class DraftResponse(BaseModel):
    id: UUID
    story_id: UUID
    format: str
    content: Any
    model: Optional[str]
    prompt_version: Optional[str]
    status: str
    created_at: Optional[str]

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_model(cls, draft: Draft) -> "DraftResponse":
        return cls(
            id=draft.id,
            story_id=draft.story_id,
            format=draft.format,
            content=draft.content,
            model=draft.model,
            prompt_version=draft.prompt_version,
            status=draft.status,
            created_at=draft.created_at.isoformat() if draft.created_at else None,
        )


class DraftPatch(BaseModel):
    status: Optional[str] = None
    content: Optional[Any] = None


# ---------------------------------------------------------------------------
# Routes — Health + Stories
# ---------------------------------------------------------------------------

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
    asyncio.create_task(run_pipeline(target_niche))
    return {"message": f"Scrape pipeline triggered for niche '{target_niche}'"}


# ---------------------------------------------------------------------------
# Routes — Draft generation
# ---------------------------------------------------------------------------

@app.post("/stories/{story_id}/generate", response_model=list[DraftResponse], status_code=201)
async def generate_drafts(story_id: UUID, db: AsyncSession = Depends(get_db)):
    """Generate a text_post and a thread draft for the given story via Claude."""
    result = await db.execute(select(Story).where(Story.id == story_id))
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    try:
        niche_config = _load_niche_config(story.niche)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail=f"Niche config not found: {story.niche}")

    from generation.claude_client import generate_all_drafts
    try:
        draft_data_list = await generate_all_drafts(story, niche_config)
    except Exception as e:
        logger.error("Draft generation failed for story %s: %s", story_id, e)
        raise HTTPException(status_code=502, detail=f"Claude generation failed: {e}")

    drafts = []
    for data in draft_data_list:
        draft = Draft(
            story_id=story.id,
            format=data["format"],
            content=data["content"],
            model=data["model"],
            prompt_version=data["prompt_version"],
            status="pending",
        )
        db.add(draft)
        drafts.append(draft)

    story.status = "selected"
    await db.commit()
    for draft in drafts:
        await db.refresh(draft)

    return [DraftResponse.from_orm_model(d) for d in drafts]


# ---------------------------------------------------------------------------
# Routes — Drafts CRUD
# ---------------------------------------------------------------------------

@app.get("/drafts", response_model=list[DraftResponse])
async def get_drafts(
    status: str = Query(default=None),
    story_id: UUID = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    q = select(Draft).order_by(desc(Draft.created_at)).limit(limit)
    if status:
        q = q.where(Draft.status == status)
    if story_id:
        q = q.where(Draft.story_id == story_id)
    result = await db.execute(q)
    drafts = result.scalars().all()
    return [DraftResponse.from_orm_model(d) for d in drafts]


@app.get("/drafts/{draft_id}", response_model=DraftResponse)
async def get_draft(draft_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Draft).where(Draft.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return DraftResponse.from_orm_model(draft)


@app.patch("/drafts/{draft_id}", response_model=DraftResponse)
async def update_draft(draft_id: UUID, patch: DraftPatch, db: AsyncSession = Depends(get_db)):
    """Update draft status and/or content (for inline edits before approval)."""
    result = await db.execute(select(Draft).where(Draft.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    valid_statuses = {"pending", "approved", "discarded", "posted"}
    if patch.status is not None:
        if patch.status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
        draft.status = patch.status

    if patch.content is not None:
        draft.content = patch.content

    await db.commit()
    await db.refresh(draft)
    return DraftResponse.from_orm_model(draft)
