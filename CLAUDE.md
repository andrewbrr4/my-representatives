# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

MyReps — a full-stack app where a user enters their address and gets a list of representatives (municipal, state, federal) with on-demand AI-researched summaries. No auth. Cloud SQL PostgreSQL for cost/usage tracking. Redis optional for caching. Production URL: **https://knowmyreps.org** (API: `https://api.knowmyreps.org`).

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

**Backend (FastAPI, Python 3.13+):** Main endpoints — `POST /api/representatives` (lookup), `POST /api/research` (on-demand per-rep research), `POST /api/elections` (election lookup + auto-research), `POST /api/election-research` (manual election research), `GET /api/election-research/{id}` (poll election research), `POST /api/issue-match` (classify issue query), `POST /api/issue-research` (per-rep issue stance research), `GET /api/issue-research/{id}` (poll issue research).

**Lookup flow** (`routers/representatives.py`):
1. Receives address → fans out two lookups concurrently:
   - `services/congress.py` for **federal** reps (US Senators + House Rep)
   - `services/cicero.py` for **state + municipal** reps
2. `services/congress.py` uses the Census Geocoder (free, no key) to resolve address → state + congressional district, then calls the US Congress API (`/v3/member/congress/{congress}/{state}`) to get senators and the district's House rep with full detail (photo, phone, website, party)
3. `services/cicero.py` calls Cicero API (`/v3.1/official`), maps `district_type` to `state`/`municipal` levels, filters out appointed and federal officials, returns list of `Representative` models
4. Returns sorted reps immediately as `RepresentativesResponse` — no research is triggered at lookup time

**On-demand research flow** (`routers/overview.py`):
1. `POST /api/research` accepts a `ResearchRequest` (contains one `Representative`)
2. Checks `RepCache` first (keyed by name + office + active overview version) — if cached, returns immediately with `status: "complete"` + summary
3. Creates task in `InMemoryResearchStore`, spawns `asyncio.create_task` for background research
4. Background task calls `research_representative(rep, store, research_id)` from the active overview package (`research/overview/`) — persists costs via `save_research_task()` + `save_transactions()`, tagging `task_type=f"rep:{ACTIVE_VERSION}"` so v1/v2/v3 usage is distinguishable in the DB
5. `GET /api/research/{research_id}` — client polls for task progress, returns `ResearchResponse` with partial summary (shape depends on version: v1 streams per-section; v2/v3 return a single `bullets` payload once synthesis/distillation finishes)
6. Task status transitions: `"pending"` → `"in_progress"` → `"complete"`. Frontend dispatches rendering on response shape in `components/overview/index.tsx` (`isBullets` switches between v1's section view and the shared bullets view).

**Rep overview pipeline** lives in `research/overview/` and is versioned. The active version is selected at import time via the `OVERVIEW_PIPELINE_VERSION` env var (`v1` default, `v2`, `v3`). Each version package exports `ResearchSummary`, `research_representative`, and `TOTAL_SECTIONS`. All variants use LangChain + Langfuse tracing with version-prefixed `@observe` names (e.g. `v1-research-pipeline`, `v2-synthesis`, `v3-distill`) and a `UsageTracker` callback (`research/usage.py`) for token/tool-call accounting. See `docs/rep-overview-versions.md` for the rationale behind each version.
- **v1** (`research/overview/v1/`) — 5 per-section research agents (policy_positions, recent_legislative_record, accomplishments, controversies, top_donors) run concurrently. Each uses a Tavily `web_search` tool, is capped at 5 searches / `recursion_limit=15`, and writes its result to `InMemoryResearchStore` as it completes, so the frontend streams sections in. Prompts in `research/overview/v1/prompts/`.
- **v2** (`research/overview/v2/`) — same 5 section agents, but results are fed into a dossier + unified citation pool and a single non-tool synthesis call produces 5–8 blended bullets with inline `[N]` markers. `TOTAL_SECTIONS=1` (store completes once at the end). Prompts in `research/overview/v2/prompts/`; dossier logic in `v2/synthesis_input.py`.
- **v3** (`research/overview/v3/`) — breadth-first retrieval: 1 LLM call generates ~15 queries, parallel Tavily fan-out (no LLM in the loop), `prefilter.py` dedupes/truncates, then one distillation call emits bullets + citations. `TOTAL_SECTIONS=1`. Prompts in `research/overview/v3/prompts/`. Tunable via `OVERVIEW_V3_*` env vars (see below).

**Elections flow** (`routers/elections.py`):
1. `POST /api/elections` receives address → calls Google Civic API (`services/elections.py`) for upcoming elections, contests, candidates, and voter info
2. Auto-triggers election research for up to 3 elections (checks election cache first)
3. Returns `ElectionsResponse` with elections + `research_ids` map so frontend knows which tasks to poll
4. `POST /api/election-research` — manually trigger research for a single election
5. `GET /api/election-research/{id}` — poll for election research progress

**Election research pipeline** (`research/election_pipeline.py`) runs **1 section**:
- `ballot_overview` — sync LLM call (no web search), generates a paragraph explaining the ballot contents from training data
- Prompt in `research/prompts/election_ballot_overview.txt`
- `ELECTION_TOTAL_SECTIONS = 1` — used when creating `InMemoryResearchStore` tasks
- `ElectionResearchSummary` has flat `citations` list (not per-section like `ResearchSummary`)

**Issue research flow** (`routers/issues.py`):
1. `POST /api/issue-match` accepts a user's free-text issue query (e.g., "housing affordability"), classifies it against an issues taxonomy stored in Postgres via `get_issues_taxonomy()`. Returns `IssueMatchResponse` with matched issue ID/label, or a rejection message.
2. `POST /api/issue-research` accepts an `IssueResearchRequest` (one rep + issue). Checks issue cache first, then spawns background research.
3. `GET /api/issue-research/{id}` — poll for issue research progress.

**Issue research pipeline** (`research/issue_pipeline.py`):
- `match_issue()` — structured LLM call to classify user query against taxonomy (no web search)
- `research_issue_stance()` — one research agent with Tavily web search, finds the rep's stance on the issue. Returns `ListSectionResult` (bulleted items + citations).
- `ISSUE_TOTAL_SECTIONS = 1`
- Prompts in `research/prompts/issue_match_system.txt`, `issue_stance_system.txt`, `issue_stance_user.txt`

**Google Civic API service** (`services/elections.py`):
- Calls `voterinfo` endpoint for election data, contests, candidates
- Parses voter info from `state[].electionAdministrationBody` (registration URLs, absentee info, early vote sites, drop-off locations)
- `_infer_election_type()` checks "runoff" before "primary" (a "primary runoff" → runoff)
- `address_hash()` for deterministic cache keys

**Store layer** (`store/`):
- `interfaces.py` — `RepCacheInterface` and `ElectionCacheInterface` ABCs
- `research_store.py` — `InMemoryResearchStore` for tracking research tasks (TTL-based cleanup). Parameterized: `total_sections` per task (5 for reps, 1 for elections, 1 for issues), `summary` type is generic `PydanticBaseModel`. `complete_section()` uses `hasattr` to handle per-section citations (rep) vs flat citations (election)
- `redis.py` — `RedisRepCache` and `RedisElectionCache` (used when `REDIS_URL` is set)
- `dependencies.py` — lazy singletons: `get_rep_cache()`, `get_election_cache()`, `get_issue_cache()`, `get_research_store()`

**Database** (`db.py`) manages an `asyncpg` connection pool (lazy singleton) for Cloud SQL PostgreSQL. Supports two connection modes: `DB_SOCKET_PATH` for Unix socket (Cloud Run with Cloud SQL proxy sidecar) or `DATABASE_URL` DSN (local dev via Cloud SQL Auth Proxy). Contains `save_research_task()` for persisting research usage data (including model, token costs, search tool, cost per search, environment, and `task_type` — `"rep:v1"` / `"rep:v2"` / `"rep:v3"` for overview research, `"election"`, or `"issue"`; the suffix encodes the overview pipeline version), `save_transactions()` for writing LLM/search cost outflows to the `transactions` ledger, and `get_issues_taxonomy()` for loading the issues classification taxonomy. The pool is created on first use and closed on app shutdown. SQL migrations live in `migrations/`.

All models are in `backend/models.py`. Backend imports use bare module names (not relative) since uvicorn runs from the `backend/` directory.

**Frontend (React + TypeScript + Vite + Tailwind v4 + shadcn/ui + React Router v7 + TanStack Query v5):** Multi-page app with React Router. Routes: `/` (search), `/reps` (representatives), `/elections` (upcoming elections). Address state shared via `AddressContext`. Routes `/reps` and `/elections` are guarded by `RequireAddress` — redirects to `/` if no address. TanStack Query provides client-side caching — data persists across route changes so switching tabs is instant.

- `src/main.tsx` — wraps app in `BrowserRouter` + `QueryClientProvider` + `AddressProvider`
- `src/lib/queryClient.ts` — `QueryClient` singleton (retry: 1, refetchOnWindowFocus: false)
- `src/App.tsx` — React Router routes with `RequireAddress` guard and `ResultsLayout` wrapper
- `src/contexts/AddressContext.tsx` — shared address state; `setAddress` navigates to `/reps`, `clearAddress` navigates to `/`
- `src/components/TabNav.tsx` — `NavLink`-based tab bar for `/reps` and `/elections`
- `src/pages/SearchPage.tsx` — landing page with welcome message and address input
- `src/pages/RepresentativesPage.tsx` — representative results grouped by level (federal/state/municipal)
- `src/pages/ElectionsPage.tsx` — elections tab; fetches elections on mount, auto-polls election research, converts candidates to reps for candidate research
- `src/hooks/useRepresentativesQuery.ts` — TanStack Query hook for rep lookup; cache key `["representatives", address]`, staleTime 5min
- `src/hooks/useElectionsQuery.ts` — TanStack Query hook for elections lookup; cache key `["elections", address]`, staleTime 5min
- `src/hooks/useResearchQuery.ts` — manages per-rep on-demand research state; uses `queryClient.setQueryData` for cache persistence, manual `setInterval` polling for in-progress research, keyed by `["research", "name|office"]`. On remount, scans cache and restarts polling for in-progress entries. Shared across reps and elections pages (candidate research uses same cache).
- `src/hooks/useElectionResearchQuery.ts` — polls election research progress per election; same cache/polling pattern as useResearchQuery, keyed by `["election-research", "name|date|address"]`
- `src/hooks/useIssueSearch.ts` — manages issue match + per-rep issue stance research; polls in-progress research, keyed by issue ID + rep
- `src/components/IssueSearch.tsx` — issue search input and per-rep stance results on the Representatives page
- `src/components/AddressSearch.tsx` — address input form
- `src/components/RepCard.tsx` — representative card with research button. Exports `ResearchContent` and `renderInline` for reuse. During loading, all section headings appear immediately with skeleton placeholders; sections render in display order (a section stays skeleton until all preceding sections are complete, so the user always sees a top-down fill even though agents complete out-of-order). Research results are collapsible.
- `src/components/ElectionCard.tsx` — election card with AI ballot overview, polling location, voter info, ballot contests.
- `src/components/CandidateCard.tsx` — compact candidate card reusing `ResearchContent` from RepCard (inherits ordered section rendering)
- `src/components/SkeletonCard.tsx` — loading placeholder
- `src/types/index.ts` — TypeScript interfaces mirroring backend Pydantic models (rep + election types)
- `src/components/ui/` — shadcn components (owned copies, not library imports)
- `@/` path alias maps to `src/` (configured in both vite.config.ts and tsconfig.app.json)

Frontend talks to backend via `fetch()` to `http://localhost:8000`. CORS is configured in `backend/main.py`.

## Environment Variables

Required in `.env` at project root:
- `ANTHROPIC_API_KEY`
- `TAVILY_API_KEY`
- `CICERO_API_KEY` — [cicerodata.com](https://www.cicerodata.com/) (paid, state + municipal elected official data)
- `US_CONGRESS_API_KEY` — [api.congress.gov](https://api.congress.gov/) (free, federal legislators)
- `GOOGLE_CIVIC_API_KEY` — Google Civic Information API v2 for election/ballot data via `voterinfo` endpoint
- `VITE_GOOGLE_PLACES_API_KEY` — Google Places API key for address autocomplete (frontend env var in `frontend/.env`; must have Places API (New) enabled in GCP console; restrict by HTTP referrer for security)
- `CLAUDE_MODEL` — model ID for the research agent (e.g. `claude-sonnet-4-20250514`)
- `SEARCH_TOOL` — which search provider is in use (default `tavily`). Recorded in the `research_tasks` table for cost tracking.
- `RESEARCH_MAX_TOKENS` — max token output for each section research agent
- `OVERVIEW_PIPELINE_VERSION` — which rep overview pipeline to run: `v1` (default, 5 section agents), `v2` (sections → synthesis bullets), or `v3` (static-query fan-out → distill bullets). Read at import time by `research/overview/__init__.py`; also encoded into `research_tasks.task_type` (`rep:v1`/`rep:v2`/`rep:v3`) and into Langfuse trace names.
- `OVERVIEW_V3_NUM_QUERIES` — v3 only: number of search queries to generate (default `15`)
- `OVERVIEW_V3_RESULTS_PER_QUERY` — v3 only: Tavily results per query (default `5`)
- `OVERVIEW_V3_SEARCH_CONCURRENCY` — v3 only: max in-flight Tavily calls (default `5`)
- `OVERVIEW_V3_RESULTS_CEILING` — v3 only: cap on total results fed to distillation (default `60`)
- `OVERVIEW_V3_SNIPPET_CHAR_CAP` — v3 only: max chars per snippet before distillation (default `800`)
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
