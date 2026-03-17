# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

MyReps — a full-stack app where a user enters their address and gets a list of representatives (municipal, state, federal) with AI-researched summaries. No auth. Cloud SQL PostgreSQL for cost/usage tracking. Redis optional for caching.

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

**Backend (FastAPI, Python 3.13+):** Single endpoint `POST /api/representatives`.

Request flow:
1. `routers/representatives.py` receives address → fans out two lookups concurrently:
   - `services/congress.py` for **federal** reps (US Senators + House Rep)
   - `services/cicero.py` for **state + municipal** reps
2. `services/congress.py` uses the Census Geocoder (free, no key) to resolve address → state + congressional district, then calls the US Congress API (`/v3/member/congress/{congress}/{state}`) to get senators and the district's House rep with full detail (photo, phone, website, party)
3. `services/cicero.py` calls Cicero API (`/v3.1/official`), maps `district_type` to `state`/`municipal` levels, filters out appointed and federal officials, returns list of `Representative` models
4. `routers/representatives.py` streams results via **Server-Sent Events** (SSE, via `sse-starlette`), with research decoupled from the connection:
   - Sends all reps immediately (without summaries) as a `representatives` event
   - Creates a job in the in-memory `JobStore` and sends a `job` event with the `job_id`
   - Spawns research as fire-and-forget `asyncio.create_task` — results write to `JobStore` + `RepCache` regardless of SSE connection
   - SSE generator polls `JobStore` every 0.5s, yielding `research` events as they complete
   - If the client disconnects, research keeps running; client can poll `GET /api/jobs/{job_id}` to recover
   - `RepCache` (in-memory, 24h TTL) avoids redundant AI calls for previously-researched reps
5. `research/pipeline.py` runs **7 per-section research agents** concurrently using LangChain + Langfuse tracing:
   - Each section (background, policy_positions, recent_legislative_record, accomplishments, controversies, recent_press, top_donors) has its own focused agent (`ChatAnthropic` with `CLAUDE_MODEL` env var) that uses a Tavily `web_search` tool and returns structured output with per-section citations
   - Section prompts are stored in `research/prompts/` (system + user template per section)
   - Each agent is limited to 5 web searches and `recursion_limit=15`
   - A separate `UsageTracker` callback handler (`research/usage.py`) runs alongside Langfuse on each agent, tracking input/output tokens and tool calls independently
   - Per-rep usage is aggregated and logged; per-job totals are persisted to the `jobs` table in Postgres via `db.py`
6. Results are sorted by level priority before streaming

7. `routers/jobs.py` exposes `GET /api/jobs/{job_id}` — returns current job state (reps, per-rep research status/summaries, overall status) for polling fallback
8. `store/` contains ABC interfaces (`interfaces.py`), in-memory implementations (`memory.py`), and Redis implementations (`redis.py`) for `JobStore` and `RepCache`, with lazy singletons in `dependencies.py`. When `REDIS_URL` is set, Redis is used; otherwise falls back to in-memory.
9. `db.py` manages an `asyncpg` connection pool (lazy singleton) for Cloud SQL PostgreSQL. Contains `save_job()` for persisting per-request usage data and `save_transactions()` for writing Anthropic/Tavily cost outflows to the `transactions` ledger. The pool is created on first use and closed on app shutdown. SQL migrations live in `migrations/`.

All models are in `backend/models.py`. Backend imports use bare module names (not relative) since uvicorn runs from the `backend/` directory.

**Frontend (React + TypeScript + Vite + Tailwind v4 + shadcn/ui):** Single-page app with two states: search and results.

- `src/hooks/useRepresentatives.ts` — manages API call state (loading, error, data); captures `job_id` from SSE and falls back to polling `GET /api/jobs/{job_id}` on disconnect
- `src/components/AddressSearch.tsx` — address input form
- `src/components/RepCard.tsx` — representative card with photo, badge, summary, contacts
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
- `US_CONGRESS_REPS_ONLY` — set to `true` to skip Cicero API and only return US congressional reps (useful for faster testing)
- `RESEARCH_MAX_TOKENS` — max token output for each section research agent
- `LANGFUSE_SECRET_KEY` — Langfuse tracing secret key
- `LANGFUSE_PUBLIC_KEY` — Langfuse tracing public key
- `LANGFUSE_BASE_URL` — Langfuse tracing base URL
- `REP_CACHE_TTL_SECONDS` — how long cached research stays valid (default `86400` / 24h)
- `JOB_TTL_SECONDS` — how long job state is kept in memory (default `1800` / 30min)
- `DISABLE_REP_CACHE` — set to `true` to skip research cache globally (useful for testing pipeline changes)
- `REDIS_URL` — Redis connection URL (e.g. `redis://localhost:6379`). When set, uses Redis for job store and rep cache; when absent, falls back to in-memory (no Redis needed for local dev)
- `DATABASE_URL` — PostgreSQL connection URL (e.g. `postgresql://postgres:<password>@<ip>:5432/postgres`). Required for persisting job usage data to Cloud SQL. Uses `asyncpg`.
- `DB_PASSWORD` — Postgres password, referenced by `docker-compose.yml` to construct `DATABASE_URL` with `host.docker.internal`
- `ANTHROPIC_INPUT_COST_PER_M` — Anthropic input token cost in USD per million tokens (e.g. `3` for Sonnet 4)
- `ANTHROPIC_OUTPUT_COST_PER_M` — Anthropic output token cost in USD per million tokens (e.g. `15` for Sonnet 4)
- `TAVILY_COST_PER_SEARCH` — Tavily cost per search in USD (e.g. `0.008`)

Backend loads these via `python-dotenv` at startup.
