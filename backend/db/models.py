import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Text, Float, Boolean, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Story(Base):
    __tablename__ = "stories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    niche = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    url = Column(Text, unique=True, nullable=False)
    source = Column(Text, nullable=False)
    summary = Column(Text)
    full_text = Column(Text)
    published_at = Column(TIMESTAMP(timezone=True))
    fetched_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    relevance_score = Column(Float, default=0)
    status = Column(Text, default="new")  # new | selected | skipped

    drafts = relationship("Draft", back_populates="story")


class Draft(Base):
    __tablename__ = "drafts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_id = Column(UUID(as_uuid=True), ForeignKey("stories.id"))
    format = Column(Text, nullable=False)  # text_post | thread | caption
    content = Column(JSONB, nullable=False)
    model = Column(Text)
    prompt_version = Column(Text)
    status = Column(Text, default="pending")  # pending | approved | discarded | posted
    created_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))

    story = relationship("Story", back_populates="drafts")
    post_logs = relationship("PostLog", back_populates="draft")


class PostLog(Base):
    __tablename__ = "post_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    draft_id = Column(UUID(as_uuid=True), ForeignKey("drafts.id"))
    final_content = Column(JSONB)
    posted_at = Column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    notes = Column(Text)

    draft = relationship("Draft", back_populates="post_logs")


class NicheProfile(Base):
    __tablename__ = "niche_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    config = Column(JSONB, nullable=False)
    active = Column(Boolean, default=False)
