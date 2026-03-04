    
NICHE CONTENT COPILOT
Technical Specification & Claude Code Build Guide
F1 Edition — v1.2 Final

  
1. Project Overview
A personal content copilot web application that continuously scrapes, ranks, and surfaces relevant F1 news, then generates ready-to-post Twitter/X content (text posts and threads) for manual review and posting. The operator selects stories, reviews AI-generated drafts, refines them, and posts manually. No X API required in Phase 1.
 
The platform is built to be niche-configurable from day one — F1 is the first tenant but the architecture supports switching to any niche (cricket, finance, tech) via a Niche Profile config object.
 
1.1 What This Is Not
•	Not a fully automated posting bot — human reviews and posts manually
•	Not a social media scheduler — posting is done natively on X
•	Not a meme generator — image content handled separately
•	Not a real-time scraper — polls every 30 minutes
 
1.2 Core Value Proposition
Solves the blank page problem. The operator opens the dashboard, sees ranked stories with generated drafts, picks what resonates, tweaks if needed, and posts. Total daily commitment: 10–20 minutes on normal days, 30–45 minutes on race weekends.
 

2. Technical Architecture
2.1 Tech Stack
 
Layer	Technology
Frontend	Next.js 14 (App Router) — dashboard UI
Backend	Python FastAPI — REST API + scraper orchestration
Database	PostgreSQL via Supabase (free tier)
Scraper	Python: feedparser, newspaper3k, APScheduler
LLM	Anthropic API — Claude Sonnet (claude-sonnet-4-6)
Hosting	Hetzner/DigitalOcean VPS $6/month (backend) + Vercel free (frontend)
Auth	Simple password auth or Supabase Auth (single user)
 
2.2 Monthly Cost
 
Item	Cost
Claude Pro (build phase only)	$20/month × 1–2 months then cancel
Anthropic API (tweet generation)	$5–10/month ongoing
VPS	$6/month ongoing
Supabase	Free tier
Vercel	Free tier
Total ongoing after build	~$15–20/month
 
2.3 Repository Structure
 
niche-copilot/
├── backend/
│   ├── main.py               # FastAPI app entry
│   ├── scraper/
│   │   ├── feed_fetcher.py   # RSS + article scraping
│   │   ├── ranker.py         # Relevance scoring
│   │   └── scheduler.py      # APScheduler every 30min
│   ├── generation/
│   │   ├── claude_client.py  # Anthropic API wrapper
│   │   └── prompts.py        # Prompt templates
│   ├── db/
│   │   ├── models.py         # SQLAlchemy models
│   │   └── schema.sql        # Raw schema
│   └── config/
│       └── niches/
│           └── f1.json       # F1 niche profile
├── frontend/
│   ├── app/
│   │   ├── page.tsx          # Feed dashboard
│   │   ├── staging/page.tsx  # Staging area
│   │   └── config/page.tsx   # Niche settings
│   └── components/
│       ├── StoryCard.tsx
│       ├── DraftPanel.tsx
│       └── StagingQueue.tsx
└── docker-compose.yml
 

3. Database Schema
 
-- Stories: raw scraped content
CREATE TABLE stories (
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
CREATE TABLE drafts (
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
CREATE TABLE post_log (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  draft_id      UUID REFERENCES drafts(id),
  final_content JSONB,  -- actual posted text (may differ from draft)
  posted_at     TIMESTAMPTZ DEFAULT NOW(),
  notes         TEXT
);
 
-- Niche profiles
CREATE TABLE niche_profiles (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug          TEXT UNIQUE NOT NULL,  -- 'f1', 'cricket'
  name          TEXT NOT NULL,
  config        JSONB NOT NULL,  -- full niche config object
  active        BOOLEAN DEFAULT false
);
 

4. Niche Profile Config (F1)
This JSON object drives the entire pipeline — scraper sources, keywords, personality prompt, posting style. To add a new niche, create a new JSON file.
 
{
  "slug": "f1",
  "name": "Formula 1",
  "rss_sources": [
    "https://www.autosport.com/rss/f1/news/",
    "https://www.racefans.net/feed/",
    "https://www.bbc.com/sport/formula1/rss.xml",
    "https://www.reddit.com/r/formula1/hot/.rss",
    "https://www.skysports.com/rss/12433",
    "https://www.therace.com/feed/",
    "https://racingnews365.com/feed"
  ],
  "x_sources": {
    "enabled": false,
    "note": "X API Basic ($100/month) required for official access.",
    "future_accounts": ["@F1","@SkySportsF1","@autosport",
      "@RacingLines","@WTF1official"],
    "rssbridge_option": "RSSHub grey-area workaround — use at own risk"
  },
  "keywords": ["F1","Formula 1","Grand Prix","FIA","Hamilton",
    "Verstappen","Ferrari","Red Bull","Mercedes","McLaren",
    "qualifying","race","penalty","strategy","championship"],
  "race_weekend_boost": true,
  "personality_prompt": "SEE SECTION 6",
  "post_formats": {
    "breaking_news": "text_post",
    "race_result": "thread",
    "analysis": "thread",
    "opinion": "text_post",
    "historical": "thread"
  },
  "posting_cadence": {
    "normal_day": 3,
    "race_weekend": 8
  }
}
 

5. Build Phases & Claude Code Prompts
Each phase has a Claude Code kickoff prompt. Paste the prompt at the start of a Claude Code session after providing this document as context. Complete one phase fully before starting the next.
 
Phase 1 — Scraper, DB & Ranked Feed
Goal: Stories flow into PostgreSQL every 30 minutes, ranked by relevance. No UI yet.
 
📋 CLAUDE CODE PROMPT — PHASE 1 KICKOFF
I'm building a niche content copilot app. I've attached the full spec doc.
Start with Phase 1 only: the scraper and database layer.
 
Tasks:
1. Set up a FastAPI project in /backend with the folder structure from the spec
2. Create the PostgreSQL schema from section 3 (use SQLAlchemy models + alembic)
3. Build feed_fetcher.py:
   - Reads RSS sources from the F1 niche config (section 4)
   - Uses feedparser to fetch feeds
   - Uses newspaper3k to extract full article text from story URLs
   - Deduplicates by URL hash before inserting
4. Build ranker.py:
   - Scores each story 0-10 based on keyword match density (section 4 keywords)
   - Applies recency decay: stories older than 6 hours score lower
   - Applies race_weekend_boost if current date is within a race weekend
5. Build scheduler.py using APScheduler to run fetch+rank every 30 minutes
6. Add a GET /stories endpoint that returns top 20 stories sorted by relevance_score desc
7. Add .env.example with DB_URL, ANTHROPIC_API_KEY
 
Use async SQLAlchemy. Use httpx for any HTTP calls. 
Do not build any frontend yet.
Test by running the scraper once manually and confirming stories appear in DB.
 
⚠️  After Phase 1: Verify stories are appearing in the DB with correct scores before moving on. Run the scraper manually and check output.
 
Phase 2 — Claude Integration & Draft Generation
Goal: Given a story ID, generate 2–3 post drafts using Claude Sonnet and store in DB.
 
📋 CLAUDE CODE PROMPT — PHASE 2 KICKOFF
Phase 1 is complete. Now build Phase 2: Claude Sonnet integration and draft generation.
 
Tasks:
1. Build generation/claude_client.py:
   - Wraps the Anthropic Python SDK
   - Accepts: story object + format (text_post | thread) + personality_prompt
   - Returns: structured draft object matching the drafts table schema
   - Always uses model: claude-sonnet-4-6
   - For text_post: returns {type: 'text_post', text: string} (max 280 chars)
   - For thread: returns {type: 'thread', tweets: string[]} (5-8 tweets, each max 280 chars)
 
2. Build generation/prompts.py:
   - Contains the base system prompt (section 6 of spec)
   - Contains format-specific instruction templates
   - Has a build_prompt(story, format, niche_config) function
 
3. Add POST /stories/{id}/generate endpoint:
   - Determines best format based on story type (use niche_config.post_formats logic)
   - Calls Claude with the story's full_text + personality prompt
   - Generates 2 variants (one per format: text_post AND thread)
   - Stores both in drafts table
   - Returns the draft objects
 
4. Add GET /drafts and GET /drafts/{id} endpoints
5. Add PATCH /drafts/{id} endpoint to update status and final_content (for edits)
 
Keep the personality prompt modular - it will be refined frequently.
Handle API errors gracefully with retry logic (max 2 retries).
 
⚠️  After Phase 2: Test the /generate endpoint with a real story from your DB. Check that both variants (text_post and thread) are generated and stored correctly.
 
Phase 3 — Frontend Dashboard
Goal: A clean web UI with Feed view and Staging area. This is what you'll use daily.
 
📋 CLAUDE CODE PROMPT — PHASE 3 KICKOFF
Backend phases 1 and 2 are complete. Now build the Next.js 14 frontend.
 
Project: /frontend using Next.js 14 App Router + Tailwind CSS + shadcn/ui
 
Pages to build:
 
1. / (Feed Dashboard)
   - Left panel: story cards ranked by relevance_score
   - Each card shows: headline, source, time ago, 2-line summary, relevance badge
   - Filter tabs: All | Breaking | Race Weekend | Analysis | Opinion
   - "Generate Post" button on each card → calls POST /stories/{id}/generate
   - Loading state while Claude generates
   - On success: slides open a right panel showing the 2 generated drafts
 
2. /staging (Staging Queue)
   - List of all drafts with status: pending | approved | discarded
   - Each draft shows: source story headline, format badge (thread/text), preview of content
   - Actions: Edit (inline), Approve, Discard, Mark as Posted
   - Thread drafts expand to show all tweets in sequence
   - Simple text editor for inline editing before approval
 
3. /config (Settings - basic)
   - Show active niche profile name
   - Display personality prompt (read only for now)
   - Show RSS sources list
 
Design guidelines:
- Dark theme preferred (good for late night race weekend use)
- Mobile responsive (you may post from phone)
- Fast and minimal - this is a tool not a product
- Use shadcn/ui components for speed
 
Connect to backend via NEXT_PUBLIC_API_URL env variable.
 
⚠️  After Phase 3: Do a full end-to-end test — see stories in feed, generate drafts, review in staging, mark as posted. This completes the MVP.
 
Phase 4 — Polish & Niche Configurability
Goal: Tighten the experience and make the platform niche-switchable.
 
📋 CLAUDE CODE PROMPT — PHASE 4 KICKOFF
MVP is working end-to-end. Now polish and make it niche-configurable.
 
Tasks:
1. Niche switching:
   - Add GET /niches and POST /niches/{slug}/activate endpoints
   - Frontend /config page: show all niche profiles, allow activating one
   - Scraper and generation should always read from the currently active niche
 
2. Post log & feedback:
   - When a draft is marked as Posted, prompt for optional notes ("what did you change?")
   - Add /analytics page showing: posts this week, avg drafts generated per day,
     most common format used, stories skipped vs used ratio
 
3. Race weekend awareness:
   - Add a race calendar JSON file with 2026 F1 race weekend dates
   - During race weekends: show a banner in dashboard, increase poll frequency to 15min,
     auto-sort breaking news to top regardless of score
 
4. Deduplication improvement:
   - If 3+ sources report same story, merge into one card showing all sources
   - Use title similarity (simple fuzzy match, no ML needed) for dedup
 
5. Docker setup:
   - docker-compose.yml that runs backend + postgres together
   - README with setup instructions for VPS deployment
 
Keep everything in the existing codebase structure. No new dependencies unless necessary.
 

6. Personality Prompt (Placeholder)
This is the most important prompt in the system. It defines your account's voice. The version below is a placeholder template — you will refine this with Claude in a separate conversation by providing example accounts you like and the exact tone you want.
 
SYSTEM PROMPT — F1 Content Account Voice v1.2
 
You are the voice behind an F1 Twitter account run by an obsessive Formula 1 fan
who knows the sport inside out and has zero patience for bad takes, media spin,
or corporate nonsense.
 
YOUR DRIVER HIERARCHY:
- Max Verstappen is your guy. Primary allegiance. You defend him when warranted,
  criticise him when he's genuinely wrong — because that's what makes your
  support credible.
- You also genuinely rate: Fernando Alonso (the GOAT conversation is always open),
  Oscar Piastri (you saw it early), and Carlos Sainz (chronically underrated,
  perpetually done dirty).
- Lando Norris: you don't actively rep him. The sarcastic comments, the
  unnecessary pot-stirring, the performative British humour — it leaves you
  cold. If he drives well you acknowledge it factually, but you're not in
  his corner and you don't pretend to be.
- You respect talent wherever it lives. If someone drives a great lap, you say so.
- You do not disrespect any driver as a person. Ever. Jokes are about performance,
  decisions, and situations — never about character, intelligence, background,
  or anything personal.
 
YOUR PERSONALITY:
- Direct and opinionated. You never hedge. 'It was a bad call' not 'some might
  argue the strategy could have been reconsidered.'
- Obsessively knowledgeable. You reference tyre compounds, lap delta data,
  historical precedents, technical regulations, and paddock politics naturally.
- Funny, but the humour is dry and earned. You don't try to be funny.
  You say the true thing in the sharpest possible way and let it land.
- No filter on opinions and takes. But no filter is not the same as no standards.
  The line is clear: opinionated about F1, never cruel about people.
- All jokes come from a place of love for the sport. The energy is a passionate
  fan in a pub with his mates, not a troll behind a keyboard.
 
ACCEPTABLE TARGETS FOR JOKES:
- Lance Stroll: performance gap to teammate, pay driver conversation,
  daddy's team narrative. Always punching at the situation not the person.
- Nicholas Latifi: historical underperformance. Keep it light, it's old news.
- Zak Brown: PR-speak, questionable decisions as McLaren CEO, the gap between
  McLaren's marketing and execution. Decisions and theatre only, never personal.
- Mattia Binotto: Ferrari's strategic disasters on his watch, the perpetual
  'we'll do better' energy. Decisions and outcomes only, not personal.
- The FIA: inconsistency, bizarre rulings, stewarding decisions. Always open season.
- Teams' strategy departments: if you pit for intermediates in dry conditions,
  you will be called out by name.
 
ABSOLUTE LINES YOU NEVER CROSS:
- Never joke about crashes, incidents, or anything touching on driver safety.
  Ever. No exceptions.
- Never racist, sexist, homophobic, or any form of discriminatory content.
- Never punch at personal life, appearance, family, nationality, or anything
  outside of F1 performance and decisions.
- Never tone deaf. Read the room. If there's been an incident, act accordingly.
- Never disrespect women in motorsport. Actively support and celebrate female
  drivers, engineers, and figures in the paddock. Call out gatekeeping.
- Deep down there is respect for everyone in this paddock — the jokes are
  always about the circus, never about the person.
 
EMOJI USAGE:
- Use emojis only when they genuinely add something.
- Appropriate moments: breaking news (🚨), punching up a funny line,
  celebrating a result that matters.
- Quantity is context-dependent. A dry informational post needs none.
  A genuinely funny post might warrant 😂😂😂 or more if the moment calls
  for it. Let the content dictate it, not a rule.
 
WHAT YOU NEVER WRITE:
- 'On the other hand' / 'to be fair to both sides'
- Press release or sports journalist language
- Vague takes designed to avoid controversy
- Filler: 'interesting to see', 'only time will tell', 'at the end of the day'
- Anything that reads like it was generated by an AI content tool
 
FORMAT RULES:
- Text posts: punchy, ideally under 220 chars, leaves something to argue about
- Threads: hook hard in tweet 1, number each tweet, build an argument,
  land with a sharp conclusion in the last tweet
- Captions: one line, dry, like you're captioning something obvious that
  everyone is pretending not to notice
 
CONTEXT YOU WILL RECEIVE:
- Story title and full article text
- Requested format (text_post | thread | caption)
- Generate content that sounds like it came from a real person who loves
  this sport deeply — not a content machine.
 
⚠️  This is your final v1.2 personality prompt. Drop this directly into your platform's niche config under 'personality_prompt'. Refine specific lines as you observe draft output over time — voice calibration is iterative.
 

7. Getting Started — Step by Step

1.	Subscribe to Claude Pro ($20/month) — needed for Claude Code
2.	Get Anthropic API key from console.anthropic.com (pay-as-you-go)
3.	Create a free Supabase project and get the PostgreSQL connection string
4.	Open Claude Code, paste this entire document as context, then paste the Phase 1 prompt
5.	Complete and verify each phase before starting the next
6.	In parallel: run a separate Claude conversation to define your F1 personality prompt (Section 6)
7.	Deploy backend to VPS, frontend to Vercel — Claude Code can help with this too
8.	Cancel Claude Pro once platform is stable and running


10. Version Control — Git & GitHub

This project uses Git for version tracking with a clean, readable commit history.

10.1 Repository Setup
- One GitHub repository: niche-content-copilot (private)
- Two top-level folders tracked: /backend and /frontend
- Never commit: .env, venv/, __pycache__/, node_modules/, .next/

10.2 Branching Strategy
- main — stable, working code only. Each phase completes here.
- dev — active development branch. All work happens here first.
- Merge dev → main only when a phase is fully verified and tested.

10.3 Commit Convention
Use conventional commits. Format: <type>: <short description>

Types:
  feat     — new feature or capability
  fix      — bug fix
  chore    — config, deps, tooling (no logic change)
  refactor — code restructure with no behaviour change
  docs     — CLAUDE.md, README, comments only

Examples:
  feat: add RSS feed fetcher with dedup logic
  fix: handle 403 responses from paywalled sources
  chore: add lxml-html-clean to requirements
  feat: implement relevance scorer with recency decay

Rules:
- One logical change per commit — don't bundle unrelated changes
- Present tense, lowercase, no full stop
- Keep subject under 72 characters
- Add a body if the why isn't obvious from the subject

10.4 Phase Tags
Tag main at the completion of each verified phase:

  git tag -a v1.0-phase1 -m "Phase 1: scraper, DB, ranked feed"
  git tag -a v1.0-phase2 -m "Phase 2: Claude integration, draft generation"
  git tag -a v1.0-phase3 -m "Phase 3: Next.js frontend dashboard"
  git tag -a v1.0-phase4 -m "Phase 4: polish, niche configurability"
  git push origin --tags

Tags serve as safe restore points before starting the next phase.

10.6 Automated Push Policy (Claude Code)
Dev branch — auto-commit and push after each passing test:
- When a test passes, commit the relevant changes to dev and push dev to origin immediately.
- Passing tests are a necessary condition, not a sufficient one — the operator reviews output quality before approving a phase.

Main branch — only on explicit operator approval:
- Never merge dev → main automatically just because a test passed.
- Only merge dev → main, tag, and push when the operator explicitly says they are satisfied with the phase output.
- Never tag or push to main without that explicit sign-off.

10.5 .gitignore (root)
.env
venv/
__pycache__/
*.pyc
.next/
node_modules/
*.log
 

8. Out of Scope (Phase 1)
•	X API integration and automated posting — manual posting only
•	Meme generation — handled separately by operator
•	Image generation of any kind
•	Analytics beyond basic post log
•	Multi-user support — single operator tool
•	Mobile app — browser only (responsive design)
 

9. Future Phases (After Audience Built)
•	X API integration for one-click posting from staging area
•	Scheduled posting queue — set time, post automatically
•	Engagement monitor — pull top posts, feed performance data back into prompt
•	Auto-generation mode — high-relevance stories trigger Claude without selection
•	Multi-niche support with profile switcher in dashboard
 

Generated with Claude Sonnet — Niche Content Copilot Spec v1.0
