# Upcoming Elections Feature — Design Spec

## Overview

Add an "Upcoming Elections" tab to MyReps so users can see what's on their ballot, who's running, and get AI-generated context — all from the same address they already enter. Candidates reuse the existing RepCard and research pipeline; elections get their own lighter research pipeline for contextual summaries.

## Architecture: Lazy-Load Elections (Approach C)

Elections are a fully independent feature from the existing rep lookup. The elections API call fires only when the user navigates to the Elections tab, keeping the existing rep flow untouched and fast.

### Why lazy-load?

- Zero performance impact on the existing rep lookup
- Elections is self-contained — easy to build, test, and evolve independently
- Bounded cost: typically 1-3 elections vs 15+ reps
- Clean loading state on the elections tab

## Data Models

All new models in `backend/models.py`.

### Candidate

Reuses the same shape as `Representative` so RepCard can render both. Additional fields:

| Field | Type | Description |
|-------|------|-------------|
| name | str | Candidate name |
| office | str | Office sought (e.g., "U.S. Senate") |
| party | str \| None | Party affiliation |
| photo_url | str \| None | Photo URL (from Civic API, may be null) |
| contest_name | str | Full contest name (e.g., "U.S. Senate - Texas") |
| incumbent | bool | Whether the candidate is the incumbent |
| level | str | federal / state / municipal (consistent with `Representative.level`) |

**Research compatibility:** The frontend converts a `Candidate` to a `Representative` shape (dropping `contest_name`, `incumbent`; mapping `level` values) before POSTing to `POST /api/research`. The research pipeline only needs `name` and `office` to run its web search agents. No changes to the research endpoint or `ResearchRequest` model.

### Contest

Groups candidates under a single race.

| Field | Type | Description |
|-------|------|-------------|
| office | str | Office name |
| level | str | federal / state / municipal (consistent with `Representative.level`) |
| district_name | str \| None | District (e.g., "Texas's 25th") |
| candidates | list[Candidate] | Candidates in this race |

### Election

Top-level grouping for an election event.

| Field | Type | Description |
|-------|------|-------------|
| name | str | Election name (e.g., "2026 Texas Primary Election") |
| date | str | Election date (ISO format) |
| election_type | str | primary / general / runoff |
| polling_location | PollingLocation \| None | Nearest polling place |
| contests | list[Contest] | Races on the ballot |

### PollingLocation

| Field | Type | Description |
|-------|------|-------------|
| name | str | Location name |
| address | str | Full address |
| hours | str \| None | Polling hours |

### ElectionsResponse

| Field | Type | Description |
|-------|------|-------------|
| elections | list[Election] | All upcoming elections for this address |

### ElectionResearchSummary

The election-level research output. Different from `ResearchSummary` (which has 7 rep-specific sections).

| Field | Type | Description |
|-------|------|-------------|
| overview_and_significance | str \| None | What this election is and why it matters locally |
| key_issues_and_context | str \| None | Top issues driving races, local context |
| voter_information | str \| None | Registration deadlines, early voting, ID requirements |
| citations | list[Citation] | Sources across all sections (reuses existing `Citation` model) |

### ElectionResearchResponse

Returned by `GET /api/election-research/{research_id}`.

| Field | Type | Description |
|-------|------|-------------|
| research_id | str | Task ID |
| status | str | pending / in_progress / complete / failed |
| summary | ElectionResearchSummary \| None | Partial or complete summary |

## Backend

### New service: `services/elections.py`

Calls the Google Civic Information API v2 `voterinfo` endpoint.

- **Input:** address string
- **Output:** `ElectionsResponse`
- **API key:** `GOOGLE_CIVIC_API_KEY` (already in `.env`)
- **Mapping:** Civic API `election` → `Election`, `contest` → `Contest`, `candidate` → `Candidate`, `pollingLocation` → `PollingLocation`
- **Filtering:** Exclude elections with no contests (empty ballots)
- **Error handling:** Civic API returns 400 when no elections are upcoming — return empty `ElectionsResponse`, not an error

### New router: `routers/elections.py`

**`POST /api/elections`**
- Accepts `{ address: string }`
- Calls `services/elections.py`
- Auto-triggers election research for each election in the response
- Returns `ElectionsResponse`
- Rate-limited (same as rep lookup: 10/min)

### Election research pipeline

New lightweight research pipeline for per-election AI context. Follows the same patterns as rep research (background task, polling, incremental sections).

**Endpoint:** `POST /api/election-research`
- Accepts an election object (name, date, type, state/location context)
- Returns `{ research_id: string, status: "pending" }`

**Polling:** `GET /api/election-research/{research_id}`
- Returns `ElectionResearchResponse` (see Data Models): `research_id`, `status`, and partial `ElectionResearchSummary` with completed sections filled in as they arrive

**Sections (3, run concurrently):**

1. **Overview & Significance** — what this election is, why it matters for this area, what's at stake (balance of power shifts, redistricting impact, etc.)
2. **Key Issues & Context** — top issues driving races this cycle, local context shaping the vote
3. **Voter Information** — registration deadlines, early voting dates, ID requirements, procedural changes

**Implementation details:**
- Uses `InMemoryResearchStore` for task tracking, but `TOTAL_SECTIONS` must be parameterized. Add a `total_sections` parameter to task creation so the store knows when a 3-section election task is complete vs a 7-section rep task. The store's `complete_section()` logic and status transition (`pending` → `in_progress` → `complete`) remain the same.
- Same `UsageTracker` callback + Langfuse tracing
- Each section agent: `ChatAnthropic` + Tavily `web_search` (same as rep research)
- Fewer searches needed per section (3-4 max vs 5 for rep research)
- **Caching:** New `ElectionCacheInterface` (parallel to `RepCacheInterface`) with `get(election_name, date, address_hash)` → `ElectionResearchSummary | None` and corresponding `put()`. Implemented in Redis when `REDIS_URL` is set, no-op otherwise (same pattern as rep cache).
- **Auto-triggered** when the elections endpoint is called — no user action needed. Capped at 3 elections max per request to bound cost. If more than 3 elections are returned, only the nearest 3 get auto-researched; the rest show a "Generate election context" button.
- **Cost tracking:** Election research tasks are persisted to the existing `research_tasks` table with a `task_type` field distinguishing `"rep"` vs `"election"`. Requires a migration to add this column (nullable, defaults to `"rep"` for existing rows).

### Candidate research

No changes to the backend. The frontend converts a `Candidate` to a `Representative` shape before calling `POST /api/research` (see Data Models section). The research pipeline searches by name + office, which works for candidates.

## Frontend

### React Router

Add `react-router-dom` as a dependency. Route structure:

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | `AddressSearch` | Landing page, address input |
| `/reps` | `RepresentativesPage` | Current representatives (existing functionality) |
| `/elections` | `ElectionsPage` | Upcoming elections (new) |

### Shared state

Address and rep data live in a React context provider wrapping both routes:
- `AddressContext` — holds the searched address, persists across tab switches
- Rep data stays in `useRepresentatives` hook (unchanged)
- Election data in a new `useElections` hook (fires on Elections tab mount)

### Route guards

If a user navigates directly to `/reps` or `/elections` without an address (e.g., page refresh, direct URL), redirect to `/`. The address is stored in React context (in-memory) — no persistence to URL params or session storage. This matches the existing UX where a refresh means re-entering the address. Keeping it simple; persistence can be added later if needed.

### Navigation

Tab bar at top of results view, mapping to routes:
- **My Representatives** → `/reps`
- **Upcoming Elections** → `/elections`
- "Change address" link navigates back to `/`
- Browser back/forward works via router
- Visual treatment kept simple (functional tabs) — UX designer will refine later

### Elections page layout

Elections grouped as cards, ordered by date (nearest first):

**Each election card contains:**
1. **Header** — election type badge, name, date with countdown
2. **AI Election Context** — auto-generated research summary (3 sections, rendered incrementally as they arrive). Collapsible with "Read full analysis" link.
3. **Polling info** — location name, address, hours (from Civic API)
4. **"What's on your ballot"** — contests grouped by office:
   - Office heading (e.g., "U.S. Senate")
   - Compact candidate cards in a flex row: photo, name, party, "Generate AI Research" button
   - Candidate research expands inline (same as RepCard behavior)
5. **Referenda placeholder** — dashed border "Coming soon" for future ballot measures

**Future elections** (where candidates aren't available yet) render in a collapsed state: just the header, date, and a "Generate election preview" link.

### New hooks

**`useElections`** — manages `POST /api/elections` call:
- Fires on Elections tab mount (lazy-load)
- Holds `ElectionsResponse` data, loading, error state
- Deduplicates calls for the same address

**`useElectionResearch`** — manages per-election research polling:
- Similar pattern to `useResearch` but keyed by election name + date
- Auto-starts (no user trigger needed) since elections endpoint triggers research
- Polls `GET /api/election-research/{id}` for incremental sections

### Component reuse

- `RepCard` renders candidates with no/minimal changes — the `Candidate` model has the same display fields
- `SkeletonCard` reused for loading states
- Existing shadcn components (Card, Badge, Button, Collapsible) reused throughout

## Out of Scope (Future Work)

- **Referenda / ballot measures** — placeholder in UI, no data pipeline yet
- **Incumbent enrichment** — matching candidates to existing rep data from Congress/Cicero
- **Election reminders / notifications**
- **Historical election results**
- **UX redesign** — navigation treatment deferred to UX designer; router is in place for any direction

## Environment Variables

No new env vars needed. `GOOGLE_CIVIC_API_KEY` is already in `.env`. Research pipeline reuses existing `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `CLAUDE_MODEL`, etc.

## Risk: Civic API Data Availability

The Google Civic API `voterinfo` endpoint only returns data when elections are upcoming and election authorities have published ballot info. Outside election season, it may return empty results or 400 errors. The UI handles this gracefully with an "No upcoming elections found" state. For development/testing, we may need to use the API's `electionId` parameter to query specific known elections, or mock responses.
