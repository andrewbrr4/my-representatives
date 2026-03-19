# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

MyReps — a full-stack app where a user enters their address and gets a list of representatives (municipal, state, federal) with on-demand AI-researched summaries. No auth. Cloud SQL PostgreSQL for cost/usage tracking. Redis optional for caching.

**Read [MISSION.md](./docs/MISSION.md) and [DESIGN.md](./docs/DESIGN.md) before making any changes.** MISSION.md defines the product vision and principles. DESIGN.md captures design decisions, tradeoffs, and open challenges.

## Commands

### Backend
```bash
conda activate my-reps          # conda env already created
cd backend
uvicorn main:app --reload       # runs on :8000
```

### Frontend
```bash
cd frontend
npm run dev          # Vite dev server on :5173
npm run build        # type-check + production build
npm run lint         # ESLint
npx tsc --noEmit     # type-check only
```

### Docker
```bash
docker compose up --build    # runs both services
```

### Adding shadcn components
```bash
cd frontend && npx shadcn@latest add <component-name>
```

## Architecture

**Backend (FastAPI, Python 3.13+):** Two main endpoints — `POST /api/representatives` (lookup) and `POST /api/research` (on-demand per-rep research).

**Lookup flow** (`routers/representatives.py`):
1. Receives address → fans out two lookups concurrently:
   - `services/congress.py` for **federal** reps (US Senators + House Rep)
   - `services/cicero.py` for **state + municipal** reps
2. `services/congress.py` uses the Census Geocoder (free, no key) to resolve address → state + congressional district, then calls the US Congress API (`/v3/member/congress/{congress}/{state}`) to get senators and the district's House rep with full detail (photo, phone, website, party)
3. `services/cicero.py` calls Cicero API (`/v3.1/official`), maps `district_type` to `state`/`municipal` levels, filters out appointed and federal officials, returns list of `Representative` models
4. Returns sorted reps immediately as `RepresentativesResponse` — no research is triggered at lookup time

**On-demand research flow** (`routers/research.py`):
1. `POST /api/research` accepts a `ResearchRequest` (contains one `Representative`)
2. Checks `RepCache` first — if cached, returns immediately with `status: "complete"` + summary
3. Creates task in `InMemoryResearchStore`, spawns `asyncio.create_task` for background research
4. Background task calls `research_representative(rep, store, research_id)` from `research/pipeline.py` — each section agent writes its result to the store as soon as it finishes, persists costs via `save_research_task()` + `save_transactions()`
5. `GET /api/research/{research_id}` — client polls for task progress, returns `ResearchResponse` with partial summary (sections arrive incrementally as each agent completes)
6. Task status transitions: `"pending"` → `"in_progress"` (first section done) → `"complete"` (all 7 done). Frontend renders completed sections immediately and shows skeleton placeholders for pending ones.

**Research pipeline** (`research/pipeline.py`) runs **7 per-section research agents** concurrently using LangChain + Langfuse tracing:
- Each section (background, policy_positions, recent_legislative_record, accomplishments, controversies, recent_press, top_donors) has its own focused agent (`ChatAnthropic` with `CLAUDE_MODEL` env var) that uses a Tavily `web_search` tool and returns structured output with per-section citations
- Section prompts are stored in `research/prompts/` (system + user template per section)
- Each agent is limited to 5 web searches and `recursion_limit=15`
- Each agent writes its result to the `InMemoryResearchStore` immediately on completion via `store.complete_section()`, enabling incremental delivery to the frontend
- A separate `UsageTracker` callback handler (`research/usage.py`) runs alongside Langfuse on each agent, tracking input/output tokens and tool calls independently
- Per-rep usage is aggregated and logged; per-research-task totals are persisted to the `research_tasks` table in Postgres via `db.py`

**Store layer** (`store/`):
- `interfaces.py` — `RepCacheInterface` ABC
- `research_store.py` — `InMemoryResearchStore` for tracking single-rep research tasks (TTL-based cleanup). Supports per-section updates via `complete_section()` — each section writes independently, status auto-transitions as sections land
- `redis.py` — `RedisRepCache` (used when `REDIS_URL` is set)
- `dependencies.py` — lazy singletons: `get_rep_cache()`, `get_research_store()`

**Database** (`db.py`) manages an `asyncpg` connection pool (lazy singleton) for Cloud SQL PostgreSQL. Supports two connection modes: `DB_SOCKET_PATH` for Unix socket (Cloud Run with Cloud SQL proxy sidecar) or `DATABASE_URL` DSN (local dev via Cloud SQL Auth Proxy). Contains `save_research_task()` for persisting per-rep research usage data (including model, token costs, search tool, cost per search, and environment) and `save_transactions()` for writing LLM/search cost outflows to the `transactions` ledger. The pool is created on first use and closed on app shutdown. SQL migrations live in `migrations/`.

All models are in `backend/models.py`. Backend imports use bare module names (not relative) since uvicorn runs from the `backend/` directory.

**Frontend (React + TypeScript + Vite + Tailwind v4 + shadcn/ui):** Single-page app with two states: search and results.

- `src/hooks/useRepresentatives.ts` — manages lookup API call state (loading, error, data); pure fetch, no polling
- `src/hooks/useResearch.ts` — manages per-rep on-demand research state; keyed by `name|office`, handles POST + polling per rep, deduplicates requests. Updates partial summary on each poll so sections render incrementally.
- `src/components/AddressSearch.tsx` — address input form
- `src/components/RepCard.tsx` — representative card with photo, badge, contacts, and "Generate AI Research" button that triggers on-demand research (4 states: idle, loading, complete, failed). During loading, all section headings appear immediately with skeleton placeholders; each section's content renders as it arrives from polling. Research results are collapsible.
- `src/components/SkeletonCard.tsx` — loading placeholder
- `src/types/index.ts` — TypeScript interfaces mirroring backend Pydantic models
- `src/components/ui/` — shadcn components (owned copies, not library imports)
- `@/` path alias maps to `src/` (configured in both vite.config.ts and tsconfig.app.json)

Frontend talks to backend via `fetch()` to `http://localhost:8000`. CORS is configured in `backend/main.py`.

## Environment Variables

Required in `.env` at project root:
- `ANTHROPIC_API_KEY`
- `TAVILY_API_KEY`
- `CICERO_API_KEY` — [cicerodata.com](https://www.cicerodata.com/) (paid, state + municipal elected official data)
- `US_CONGRESS_API_KEY` — [api.congress.gov](https://api.congress.gov/) (free, federal legislators)
- `GOOGLE_CIVIC_API_KEY` — kept for future election/ballot data via `voterinfo` endpoint
- `VITE_GOOGLE_PLACES_API_KEY` — Google Places API key for address autocomplete (frontend env var in `frontend/.env`; must have Places API (New) enabled in GCP console; restrict by HTTP referrer for security)
- `CLAUDE_MODEL` — model ID for the research agent (e.g. `claude-sonnet-4-20250514`)
- `SEARCH_TOOL` — which search provider is in use (default `tavily`). Recorded in the `research_tasks` table for cost tracking.
- `RESEARCH_MAX_TOKENS` — max token output for each section research agent
- `LANGFUSE_SECRET_KEY` — Langfuse tracing secret key
- `LANGFUSE_PUBLIC_KEY` — Langfuse tracing public key
- `LANGFUSE_BASE_URL` — Langfuse tracing base URL
- `REP_CACHE_TTL_SECONDS` — how long cached research stays valid (default `259200` / 3 days)
- `JOB_TTL_SECONDS` — how long research task state is kept in memory (default `1800` / 30min)
- `DISABLE_REP_CACHE` — set to `true` to skip research cache globally (useful for testing pipeline changes)
- `REDIS_URL` — Redis connection URL (e.g. `redis://localhost:6379`). When set, uses Redis for rep cache; when absent, rep cache is a no-op (no Redis needed for local dev)
- `DATABASE_URL` — PostgreSQL connection URL (e.g. `postgresql://postgres:<password>@127.0.0.1:5432/postgres`). Used for local dev (via Cloud SQL Auth Proxy). Uses `asyncpg`.
- `DB_SOCKET_PATH` — Cloud SQL Unix socket path (e.g. `/cloudsql/my-representatives-489301:us-central1:my-representatives`). When set, `db.py` connects via Unix socket instead of `DATABASE_URL`. Used on Cloud Run where the Cloud SQL proxy sidecar provides the socket automatically.
- `DB_NAME` — Postgres database name (default `postgres`). Used with `DB_SOCKET_PATH`.
- `DB_USER` — Postgres user (default `postgres`). Used with `DB_SOCKET_PATH`.
- `DB_PASSWORD` — Postgres password. Used with `DB_SOCKET_PATH` on Cloud Run, and by `docker-compose.yml` to construct `DATABASE_URL`.
- `ANTHROPIC_INPUT_COST_PER_M` — Anthropic input token cost in USD per million tokens (e.g. `3` for Sonnet 4)
- `ANTHROPIC_OUTPUT_COST_PER_M` — Anthropic output token cost in USD per million tokens (e.g. `15` for Sonnet 4)
- `COST_PER_SEARCH` — Tavily cost per search in USD (e.g. `0.008`)
- `ENVIRONMENT` — `dev` or `prod` (default `dev`). Recorded in the `research_tasks` table for filtering.

Backend loads these via `python-dotenv` at startup.
