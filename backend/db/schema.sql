-- Stories: raw scraped content
CREATE TABLE IF NOT EXISTS stories (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  niche         TEXT NOT NULL,
  title         TEXT NOT NULL,
  url           TEXT UNIQUE NOT NULL,
  source        TEXT NOT NULL,
  summary       TEXT,
  full_text     TEXT,
  published_at  TIMESTAMPTZ,
  fetched_at    TIMESTAMPTZ DEFAULT NOW(),
  relevance_score FLOAT DEFAULT 0,
  status        TEXT DEFAULT 'new'  -- new | selected | skipped
);

-- Drafts: Claude-generated post options
CREATE TABLE IF NOT EXISTS drafts (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  story_id      UUID REFERENCES stories(id),
  format        TEXT NOT NULL,  -- text_post | thread | caption
  content       JSONB NOT NULL, -- {text: ''} or {tweets: []}
  model         TEXT,
  prompt_version TEXT,
  status        TEXT DEFAULT 'pending', -- pending|approved|discarded|posted
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Post log: what actually got posted
CREATE TABLE IF NOT EXISTS post_log (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  draft_id      UUID REFERENCES drafts(id),
  final_content JSONB,  -- actual posted text (may differ from draft)
  posted_at     TIMESTAMPTZ DEFAULT NOW(),
  notes         TEXT
);

-- Niche profiles
CREATE TABLE IF NOT EXISTS niche_profiles (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug          TEXT UNIQUE NOT NULL,  -- 'f1', 'cricket'
  name          TEXT NOT NULL,
  config        JSONB NOT NULL,  -- full niche config object
  active        BOOLEAN DEFAULT false
);
