# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

MyReps — a full-stack app where a user enters their address and gets a list of representatives (municipal, state, federal) with on-demand AI-researched summaries. No auth. Cloud SQL PostgreSQL for cost/usage tracking. Redis optional for caching. Production URL: **https://knowmyreps.org** (API: `https://api.knowmyreps.org`).

**Read [MISSION.md](./docs/MISSION.md), [DESIGN.md](./docs/DESIGN.md), and [V4_PERFORMANCE.md](./docs/initiatives/V4_PERFORMANCE.md) before making any changes.** MISSION.md defines the product vision and principles. DESIGN.md captures design decisions, tradeoffs, and open challenges. V4_PERFORMANCE.md is the **active priority initiative** — it codifies the v4 rep-overview pipeline philosophy (5-bucket taxonomy, breadth/depth/formatter responsibilities) and tracks per-node latency/quality ideas with shipped vs. open status. Read it before proposing any v4 changes or analyzing v4 traces.

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
4. Background task calls `research_representative(rep, store, research_id)` from the active overview package (`research/overview/`) — persists costs via `save_research_task()` + `save_transactions()`, tagging `task_type=f"rep:{ACTIVE_VERSION}"` so per-variant usage is distinguishable in the DB
5. `GET /api/research/{research_id}` — client polls for task progress, returns `ResearchResponse` with partial summary (shape depends on variant: legacy v1 streams per-section; the default and legacy v2/v3 return a single `bullets` payload once the formatter/synthesis/distillation finishes)
6. Task status transitions: `"pending"` → `"in_progress"` → `"complete"` (or `"failed"`). Frontend dispatches rendering on response shape in `components/overview/index.tsx` (`isBullets` switches between v1's section view and the shared bullets view). The bullets view gates the skeleton on `bullets.length === 0`; the parent card separately gates on `researchStatus === "loading"` for the user-visible "Scraping the web…" message.

**Rep overview pipeline** lives in `research/overview/`. The production default is the flat top-level package (formerly known as "v4" — LangGraph breadth + adaptive depth + structured-output formatter). The `OVERVIEW_PIPELINE_VERSION` env var (read at import time) selects which pipeline runs; default is `v4`, which resolves to the flat top-level. Legacy variants `v1` / `v2` / `v3` are still selectable for trace/cost comparison and live under `research/overview/legacy/`. They are not the focus of further iteration. The dispatch module (`research/overview/__init__.py`) re-exports `ResearchSummary`, `research_representative`, and `TOTAL_SECTIONS` from whichever variant is active. **Each variant owns its own `ResearchSummary` Pydantic model** — there is no shared overview-model module. Bullet-shaped summaries (legacy v2, v3, and the current default) all define `ResearchSummary(bullets: list[str], citations: list[Citation])` with `bullets` as a required, non-nullable list (empty list = loading state). The previously-shared `list[str] | None` generated an `anyOf[array, null]` JSON schema that occasionally caused Anthropic to emit `bullets` as a JSON-encoded string — removing the null removed the ambiguity. All variants use LangChain + Langfuse tracing with version-prefixed `@observe` names (e.g. `v1-research-pipeline`, `v2-synthesis`, `v3-distill`, `v4-formatter` — the `v4-` prefix remains on the current default's trace names as a generation marker for Langfuse continuity) and a `UsageTracker` callback (`research/usage.py`) for token/tool-call accounting. See `docs/rep-overview-versions.md` for the rationale behind each version.
- **Default** (`research/overview/`) — LangGraph-native breadth + adaptive depth. A top-level `StateGraph(V4State)` wires `query_generator → breadth_search → filter → research_agent → formatter`. **research_agent** is a structured-output triage call (not a react loop) — one LLM call returns a `_TriageOutput.depth_requests: list[_DepthRequest(topic, reason)]`, then those are dispatched concurrently via `asyncio.gather`; each spawns an isolated depth subagent. `OVERVIEW_V4_AGENT_MAX_DEPTH_CALLS` is a hard cap enforced in `research_agent.py`. (Earlier versions used `create_react_agent` here with a `request_depth_research` tool; rewritten 2026-04-30 — react steps were serial latency without buying better triage.) **Depth subagent** remains a `create_react_agent` over an isolated `DepthState`; its only tool, `depth_tavily_search`, returns `Command(update={search_results: [SearchResult], messages: [ToolMessage]})` so structured search results accumulate in `DepthState.search_results` while formatted snippets continue to drive the agent loop via `messages`. State isolation prevents the token-accumulation problem legacy v1/v2 suffered: a depth subagent's `messages` (Tavily ToolMessage snippets, agent reasoning) lives and dies in `DepthState` — only `SearchResult` lists cross back, tagged with the originating topic. **Formatter** takes `filtered_results` + `depth_search_results` (both `list[SearchResult]`, fully symmetric) and does curation+presentation in one structured-output call. Output schema is two **parallel top-level lists** indexed in lockstep — `bullet_texts: list[str]` and `bullet_sources: list[list[str]]` — never a nested `list[Bullet]`. The flat shape is what legacy v2/v3 use reliably; the original nested-list schema caused Sonnet 4.6 to stringify `bullets` as a JSON-encoded string in ~40% of runs (silent Pydantic validation failures, no user-visible output). The formatter wraps the structured-output call in LangChain's `with_retry(retry_if_exception_type=(ValidationError,), stop_after_attempt=2)` so any residual wire-shape miss gets one retry — empirically, the second attempt usually emits the correct shape. The user prompt ends with an explicit primacy/recency reminder of the wire shape (`bullet_texts` and `bullet_sources` must each be JSON arrays, not JSON-encoded strings). Citations are assembled in Python from `bullet_sources` (URL first-appearance order, deduped, looked up against the combined breadth+depth pool); URLs cited by the LLM but **not in the pool are silently dropped** in `_build_citations` (LLM hallucinates plausible URLs from training data; surfacing those would be a trust-breaker — drop count is logged for monitoring). `[N]` markers are appended to bullet text in Python — the LLM never emits markers, so there's no chance of N mismatch. **Bullet target: 6–8 bullets, ~14–22 words each** (set in `formatter_system.txt` + `formatter_user.txt`; see `docs/initiatives/V4_PERFORMANCE.md` for the iteration history that landed here). `TOTAL_SECTIONS=1`. Prompts in `research/overview/prompts/`. Tunable via `OVERVIEW_V4_*` env vars (see below) — the `V4_` env var prefix is preserved for deployment continuity. **Loading UX:** each node calls `report_step(state, "<key>")` (mapping in `research/overview/progress.py`) as its first statement, writing a `(label, pct)` to `InMemoryResearchStore.update_progress`; this surfaces on `ResearchResponse.progress` (`ProgressInfo{pct, label}`) and the 2s frontend poll drives a per-node progress bar. When formatter streaming is on (default), the formatter writes each parsed bullet to the store via `update_partial`, so the frontend flips from the progress bar + a DB-served fun-facts carousel (`facts` table → `GET /api/facts` via `routers/facts.py`/`db.get_civics_facts`, cached client-side by `useFactsQuery`) to a live bullets view (with a trailer skeleton) on the first bullet.
- **Legacy `v1`** (`research/overview/legacy/v1/`) — 5 per-section research agents (policy_positions, recent_legislative_record, accomplishments, controversies, top_donors) run concurrently. Each uses a Tavily `web_search` tool, is capped at 5 searches / `recursion_limit=15`, and writes its result to `InMemoryResearchStore` as it completes, so the frontend streams sections in. Prompts in `research/overview/legacy/v1/prompts/`.
- **Legacy `v2`** (`research/overview/legacy/v2/`) — same 5 section agents, but results are fed into a dossier + unified citation pool and a single non-tool synthesis call produces 5–8 blended bullets with inline `[N]` markers. `TOTAL_SECTIONS=1` (store completes once at the end). Prompts in `research/overview/legacy/v2/prompts/`; dossier logic in `legacy/v2/synthesis_input.py`. Section agents' outputs are NOT user-facing — their prompts only ask for plain one-sentence findings with `[N]` markers (no markdown/headlines), since synthesis rewrites everything. Synthesis LLM emits only `bullets` via a private `_SynthesisBullets` schema; the unified citation list is assembled in Python from the dossier pool, not round-tripped through the model.
- **Legacy `v3`** (`research/overview/legacy/v3/`) — breadth-first retrieval: 1 LLM call generates ~15 queries, parallel Tavily fan-out (no LLM in the loop), `prefilter.py` dedupes/truncates, then one distillation call emits bullets + citations. `TOTAL_SECTIONS=1`. Prompts in `research/overview/legacy/v3/prompts/`. Tunable via `OVERVIEW_V3_*` env vars (see below). Distillation bullets *are* user-facing, so the distill prompt specifies the `**headline** - sentence [N]` display format.

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

**Database** (`db.py`) manages an `asyncpg` connection pool (lazy singleton) for Cloud SQL PostgreSQL. Supports two connection modes: `DB_SOCKET_PATH` for Unix socket (Cloud Run with Cloud SQL proxy sidecar) or `DATABASE_URL` DSN (local dev via Cloud SQL Auth Proxy). Contains `save_research_task()` for persisting research usage data (including model, token costs, search tool, cost per search, environment, and `task_type` — `"rep:v1"` / `"rep:v2"` / `"rep:v3"` / `"rep:v4"` for overview research, `"election"`, or `"issue"`; the suffix encodes the overview pipeline version), `save_transactions()` for writing LLM/search cost outflows to the `transactions` ledger, and `get_issues_taxonomy()` for loading the issues classification taxonomy. The pool is created on first use and closed on app shutdown. The full schema lives in `backend/schema.sql` (apply once against a fresh database — no migration history).

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

## Debugging with Langfuse

The app is fully Langfuse-instrumented. When investigating agent/LLM behavior (recursion limits, empty outputs, cost spikes, tool-call loops), pull traces via the Langfuse MCP *before* reading pipeline code — see the `langfuse-trace-debugging` skill for the workflow. Use the trace-name taxonomy below to filter `fetch_traces(name=...)`.

**Trace names** (from `@observe(name=...)` and LangChain `run_name`):
- Rep overview v1/v2: `{v}-research-pipeline`, `{v}-section-agent` + inner LangChain `run_name="{v}:{section}:{rep}"`. v2 also has `v2-synthesis` (non-tool bullet synthesis).
- Rep overview v3: `v3-research-pipeline`, `v3-query-gen`, `v3-distill` (no per-section spans — v3 fans out searches without section agents).
- Rep overview v4: `v4-research-pipeline`, `v4-query-gen`, `v4-breadth-search`, `v4-filter`, `v4-research-agent` (one span per pipeline run), `v4-formatter`. Depth subagent runs are nested LangChain spans under the research_agent span (no top-level `@observe` on the depth subgraph — its work is part of the research_agent's trace tree).
- Elections: `election-ballot-overview` (single sync LLM span).
- Issues: `issue-match` (taxonomy classifier), `issue-stance-agent` (Tavily-backed per-rep research).

**Cross-reference to the DB:** `research_tasks.task_type` encodes the pipeline variant — `rep:v1` / `rep:v2` / `rep:v3` / `rep:v4` / `election` / `issue`. `rep:v4` is the current default; the other `rep:vN` rows come from legacy A/B runs. Use traces for "what happened in one run" and Postgres (`research_tasks`, `transactions`) for cross-run cost/token aggregates. The pipeline version came from the `OVERVIEW_PIPELINE_VERSION` env var at import time (default `v4`), so a trace's name prefix and its `task_type` suffix must agree — mismatches mean a bad deploy or env change mid-session.

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
- `TAVILY_EXCLUDE_DOMAINS` — comma-separated list of domains to exclude from all Tavily searches (applied via Tavily's `exclude_domains` param in `research/search.py`). When unset, falls back to `_DEFAULT_EXCLUDE_DOMAINS` (social/video + party committees). Set to empty string to disable filtering. Affects every pipeline that calls `web_search` or `tavily_search_raw` (v1/v2 section agents, v3 breadth, v4 breadth + depth, elections, issues).
- `TAVILY_GLOBAL_CONCURRENCY` — global semaphore cap on concurrent Tavily calls across the *entire process* (default `20`). Every pipeline funnels through `research/search.py:_search_semaphore`, so this is the hard ceiling that overrides per-pipeline caps like `OVERVIEW_V4_SEARCH_CONCURRENCY`. Tavily's paid tier supports ~100 RPS; the historical default of 3 was strangling breadth fan-out. Lower this to protect against rate limits at the cost of latency; raising past Tavily's per-tier limit just triggers the existing exponential-backoff retry path on 429s.
- `RESEARCH_MAX_TOKENS` — max token output for each section research agent
- `OVERVIEW_PIPELINE_VERSION` — selects which rep-overview pipeline to run. **Default `v4`** (the flat top-level pipeline at `research/overview/` — LangGraph breadth + adaptive depth). Legacy values `v1` (per-section streaming), `v2` (sections → synthesis bullets), `v3` (static-query fan-out → distill bullets) load from `research/overview/legacy/`. Read at import time by `research/overview/__init__.py`; encoded into `research_tasks.task_type` (`rep:v1`/`rep:v2`/`rep:v3`/`rep:v4`) and into Langfuse trace names. Prod sets `v4` explicitly on Cloud Run for visibility, but the code default is also `v4`.
- `OVERVIEW_V3_NUM_QUERIES` — v3 only: number of search queries to generate (default `15`)
- `OVERVIEW_V3_RESULTS_PER_QUERY` — v3 only: Tavily results per query (default `5`)
- `OVERVIEW_V3_SEARCH_CONCURRENCY` — v3 only: max in-flight Tavily calls (default `5`)
- `OVERVIEW_V3_RESULTS_CEILING` — v3 only: cap on total results fed to distillation (default `60`)
- `OVERVIEW_V3_SNIPPET_CHAR_CAP` — v3 only: max chars per snippet before distillation (default `800`)
- `OVERVIEW_V4_NUM_QUERIES` — v4 only: number of breadth queries (default `18`)
- `OVERVIEW_V4_RESULTS_PER_QUERY` — v4 only: Tavily results per query (default `5`)
- `OVERVIEW_V4_SEARCH_CONCURRENCY` — v4 only: max in-flight Tavily calls (default `5`)
- `OVERVIEW_V4_RESULTS_CEILING` — v4 only: cap on total results fed to research_agent (default `60`)
- `OVERVIEW_V4_SNIPPET_CHAR_CAP` — v4 only: max chars per snippet (default `800`)
- `OVERVIEW_V4_AGENT_MAX_DEPTH_CALLS` — v4 only: max depth-research calls per pipeline run (default `3`). **Hard cap enforced in `research_agent.py`** — `_TriageOutput.depth_requests` is truncated to this many before the `asyncio.gather` fanout. Also substituted into the triage prompt as a soft signal. Use `OVERVIEW_V4_DEPTH_ENABLED=false` to actually skip the depth path entirely.
- `OVERVIEW_V4_DEPTH_ENABLED` — v4 only: when `false`, the research_agent node short-circuits to an empty depth result and skips the triage LLM call + depth subagents entirely (default `true`). Use to A/B breadth-only vs. breadth+depth, or to cut latency when depth isn't needed.
- `OVERVIEW_V4_DEPTH_RECURSION_LIMIT` — v4 only: recursion limit per depth subagent (default `8`)
- `OVERVIEW_V4_QUERY_GEN_MODEL` — v4 only: model ID for the query_generator node. Falls back to `CLAUDE_MODEL`. Use to A/B Haiku for the simple list-of-queries output.
- `OVERVIEW_V4_TRIAGE_MODEL` — v4 only: model ID for the research_agent (triage) node. Falls back to `CLAUDE_MODEL`. Triage just picks topics+reasons (or skips); a smaller model is plausible.
- `OVERVIEW_V4_DEPTH_MODEL` — v4 only: model ID for the depth subagent. Falls back to `CLAUDE_MODEL`. Each depth subagent runs ~3 LLM calls in its react loop, so model swap here is leveraged.
- `OVERVIEW_V4_FORMATTER_MODEL` — v4 only: model ID for the formatter node. Falls back to `CLAUDE_MODEL`. Formatter is the second-biggest latency contributor in v4 (~26s with 23k input tokens), so smaller-model A/B is high-leverage.
- `OVERVIEW_V4_FORMATTER_STREAMING` — v4 only: when `true` (default), the formatter streams bullets as NDJSON (one `{"text","sources"}` object per line) via `model.astream`, parsing each line and writing the accumulating partial summary to the research store via `update_partial`, so the frontend renders bullets as they land. When `false`, falls back to the blocking `with_structured_output` path (`_formatter_structured`). The streaming path loads its own prompts (`formatter_system_streaming.txt` + `formatter_user_streaming.txt`) since the structured prompt prescribes the `bullet_texts`/`bullet_sources` tool schema; the structured path remains the escape hatch. Helpers (`_handle_line`, `_consume_stream`) live in `nodes/formatter.py`.
- `OVERVIEW_V4_FORMATTER_MIN_BULLETS` — v4 only: minimum valid bullets the streaming formatter must produce; below this the run raises (→ task `failed` → frontend retry UI) rather than showing a too-thin overview (default `3`).
- `OVERVIEW_V4_SHOW_SOURCES` — v4 only: when `true`, the formatter (a) drops depth `SearchResult`s whose URL already appears in the breadth pool or earlier in depth — a token-saver on the formatter's input — and (b) populates `summary.sources: list[SourceLink]` (deduped breadth+depth pool, projected to `{title, url}`). Frontend renders these as an expandable "Further reading (N)" list below the bullets when present. When `false` (default), the formatter behaves exactly as before (no pre-formatter dedup, empty `sources`). The pipeline also switches its task-store write from `complete_section` to `complete()` when this flag is on so the new field reaches the store. Sources are persisted in the rep cache alongside bullets/citations, so cache hits return them with no pipeline run.
- `ISSUES_SHOW_SOURCES` — issue-stance only: when `true`, swaps the agent's `web_search` tool for a per-invocation accumulating variant (`research/search.py:make_accumulating_web_search`) that records every Tavily result's `{title, url}` (deduped) onto a sidecar list. The pipeline then populates `IssueStanceSummary.further_reading: list[SourceLink]`, and the frontend renders these as an expandable "Further reading (N)" list below the issue stance bullets. No extra Tavily calls — just keeps a structured reference to results we already retrieved. The pipeline switches its task-store write from `complete_section` to `complete()` when this flag is on so the new field reaches the store; further-reading is also persisted in the issue cache alongside bullets/citations. When `false` (default), the issue pipeline behaves exactly as before.
- `LANGFUSE_SECRET_KEY` — Langfuse tracing secret key
- `LANGFUSE_PUBLIC_KEY` — Langfuse tracing public key
- `LANGFUSE_BASE_URL` — Langfuse tracing base URL
- `REP_CACHE_TTL_SECONDS` — how long cached research stays valid (default `259200` / 3 days)
- `JOB_TTL_SECONDS` — how long research task state is kept in memory (default `1800` / 30min)
- `DISABLE_REP_CACHE` — set to `true` to skip research cache globally (useful for testing pipeline changes)
- `REDIS_URL` — Redis connection URL (e.g. `redis://localhost:6379`). When set, uses Redis for rep cache; when absent, rep cache is a no-op (no Redis needed for local dev)
- `DATABASE_URL` — PostgreSQL connection URL (e.g. `postgresql://postgres:<password>@127.0.0.1:5432/postgres`). Used for local dev (via Cloud SQL Auth Proxy). Uses `asyncpg`.
- `DB_SOCKET_PATH` — Cloud SQL Unix socket path (e.g. `/cloudsql/my-representatives-489301:us-east1:my-reps-small`). When set, `db.py` connects via Unix socket instead of `DATABASE_URL`. Used on Cloud Run where the Cloud SQL proxy sidecar provides the socket automatically.
- `DB_NAME` — Postgres database name (default `postgres`). Used with `DB_SOCKET_PATH`.
- `DB_USER` — Postgres user (default `postgres`). Used with `DB_SOCKET_PATH`.
- `DB_PASSWORD` — Postgres password. Used with `DB_SOCKET_PATH` on Cloud Run, and by `docker-compose.yml` to construct `DATABASE_URL`.
- `ANTHROPIC_INPUT_COST_PER_M` — Anthropic input token cost in USD per million tokens (e.g. `3` for Sonnet 4)
- `ANTHROPIC_OUTPUT_COST_PER_M` — Anthropic output token cost in USD per million tokens (e.g. `15` for Sonnet 4)
- `COST_PER_SEARCH` — Tavily cost per search in USD (e.g. `0.008`)
- `ENVIRONMENT` — `dev` or `prod` (default `dev`). Recorded in the `research_tasks` table for filtering.
- `CORS_ORIGINS` — comma-separated list of allowed CORS origins (read in `main.py`). Defaults to `http://localhost:5173,http://localhost:3000` for local dev; prod sets the deployed frontend origin(s).
- `ADMIN_API_KEY` — gates the admin-only `/api/transactions` routes (`routers/transactions.py`). Sent by the client as the `X-Admin-Key` header and compared constant-time. **Fail-closed:** if unset, every transactions request is rejected. The frontend never calls these endpoints — only `admin.ipynb`, which must pass the header.

Backend loads these via `python-dotenv` at startup.
