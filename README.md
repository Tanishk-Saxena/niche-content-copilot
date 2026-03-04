# Niche Content Copilot — F1 Edition

A personal content copilot that scrapes, ranks, and surfaces F1 news — then generates ready-to-post Twitter/X content for manual review. Built for a single operator. No automation, no scheduling, no X API. Just a fast tool that solves the blank page problem.

---

## What It Does

1. Scrapes F1 RSS feeds every 30 minutes
2. Ranks stories by relevance, recency, and race weekend context
3. Generates tweet drafts and threads via Claude Sonnet
4. Operator reviews, edits if needed, and posts manually on X

Daily workflow: open dashboard → pick stories → review drafts → post. 10–20 minutes on normal days, more on race weekends.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 (App Router) + Tailwind + shadcn/ui |
| Backend | Python FastAPI |
| Database | PostgreSQL via Supabase |
| Scraper | feedparser + newspaper3k + APScheduler |
| LLM | Anthropic API — Claude Sonnet (claude-sonnet-4-6) |
| Hosting | VPS (backend) + Vercel (frontend) |

---

## Project Structure

```
niche-copilot/
├── backend/
│   ├── main.py                  # FastAPI app entry
│   ├── scraper/
│   │   ├── feed_fetcher.py      # RSS + article scraping
│   │   ├── ranker.py            # Relevance scoring
│   │   └── scheduler.py        # APScheduler every 30min
│   ├── generation/
│   │   ├── claude_client.py     # Anthropic API wrapper
│   │   └── prompts.py          # Prompt templates
│   ├── db/
│   │   ├── models.py            # SQLAlchemy models
│   │   └── schema.sql           # Raw schema reference
│   └── config/
│       └── niches/
│           └── f1.json          # F1 niche profile (2026 season)
├── frontend/
│   ├── app/
│   │   ├── page.tsx             # Feed dashboard
│   │   ├── staging/page.tsx     # Staging queue
│   │   └── config/page.tsx      # Niche settings
│   └── components/
│       ├── StoryCard.tsx
│       ├── DraftPanel.tsx
│       └── StagingQueue.tsx
└── docker-compose.yml
```

---

## Build Phases

| Phase | Goal | Status |
|-------|------|--------|
| 1 | Scraper, DB, ranked feed | ✅ Complete |
| 2 | Claude integration, draft generation | Pending |
| 3 | Next.js frontend dashboard | Pending |
| 4 | Polish, niche configurability, Docker | Pending |

---

## Niche Configurability

F1 is the first tenant. The entire pipeline — sources, keywords, personality, post formats — is driven by a single JSON config file. Adding a new niche (cricket, finance, tech) means adding a new config file and activating it.

The 2026 F1 config covers:
- 7 RSS sources
- 11 teams, 22 drivers
- 24-race calendar with race weekend boost logic
- Keyword scoring list

---

## Local Setup

```bash
# Backend
cd backend
python -m venv venv
venv/Scripts/activate      # Windows
# source venv/bin/activate  # macOS/Linux

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your DB_URL and ANTHROPIC_API_KEY

uvicorn main:app --reload
```

API available at `http://localhost:8000` — docs at `/docs`.

---

## API Endpoints (Phase 1)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/stories` | Top 20 stories by relevance score |
| GET | `/stories/{id}` | Single story |
| POST | `/scrape` | Manually trigger scrape pipeline |
| GET | `/health` | Health check |

---

## Version Control

- `main` — stable, verified code. Tagged at each phase completion.
- `dev` — active development branch.
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/) format.
- Phase tags: `v1.0-phase1`, `v1.0-phase2`, etc.
