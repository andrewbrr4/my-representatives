# Loading Progress + Fun Facts Design

**Status:** Spec — pending implementation
**Branch:** `formatter-streaming`
**Pipeline:** v4 rep overview (the production default at `research/overview/`)
**Related:** [2026-05-12-formatter-streaming-design.md](./2026-05-12-formatter-streaming-design.md) — the NDJSON formatter streaming this spec depends on and folds in.

## Goal

Give the user something engaging and informative to look at *before any research results land*. While a rep's AI overview is being researched, the card shows two things:

1. **A fun-facts carousel** — rotating civics/America facts, served from the database, purely for the user to read while they wait.
2. **A progress bar** — a filling bar with a percentage and a layperson-readable label describing what the pipeline is currently doing ("Searching the web", "Digging into the details", …). The label/percent advances as the LangGraph pipeline moves node to node.

Once the pipeline reaches the final node (the formatter), bullets begin **streaming** in one-by-one, and the progress+facts view is retired the instant the first bullet arrives.

## Non-goals

- No new transport. Progress and streaming bullets both ride the existing 2s polling against `InMemoryResearchStore`. No SSE/WebSocket.
- No sub-node progress granularity. Five discrete steps (one per pipeline node) is the whole resolution. Within a node the bar holds steady.
- No change to non-v4 pipelines (legacy v1/v2/v3) or non-rep pipelines (elections, issues).
- No model swap or research-quality change. This is a perceived-latency / engagement feature only.
- No admin UI for editing facts. Facts live in a DB table seeded with a starter set; editing is done directly in the DB for now.

## High-level approach

Three layers, all riding existing infrastructure:

1. **Per-node progress reporting.** Each of the five v4 nodes reports its step (a label + percent) to the research store on entry. The store carries `progress_pct` + `progress_label`; the poll endpoint surfaces them in a new `progress` field on `ResearchResponse`. The existing 2s frontend poll reads them.

2. **Bullet streaming at the formatter.** Implement the formatter NDJSON streaming from [the formatter-streaming spec](./2026-05-12-formatter-streaming-design.md), defaulted **on**. As each bullet is parsed it is written to the store via `update_partial()`; the poll picks it up. The first bullet flips the frontend from the progress+facts view to the live bullets view.

3. **Fun-facts carousel from the DB.** A `facts` table + `GET /api/facts` endpoint + a TanStack-cached frontend hook. A self-contained carousel component rotates the facts while the progress view is showing.

The frontend rendering gate that ties it together:

| Condition | Renders |
|---|---|
| `status === "loading"` and `bullets.length === 0` | `<ResearchProgress>` + `<FactsCarousel>` |
| `bullets.length > 0` and `status === "loading"` | streaming bullets + trailer skeleton |
| `status === "complete"` | final bullets, no trailer |
| `status === "failed"` | existing failure UI |

## Architecture

```
POST /api/research
  └─ router creates task (pending, progress 0/"Getting started")
  └─ pipeline_graph.ainvoke(initial={rep, usage_log, store, research_id})
        query_generator → report_step("query_generator")  →  5% "Planning what to research"
        breadth_search  → report_step("breadth_search")   → 20% "Searching the web"
        filter          → report_step("filter")           → 45% "Sorting through sources"
        research_agent  → report_step("research_agent")   → 55% "Digging into the details"
        formatter       → report_step("formatter")        → 85% "Writing the summary"
                        └─ streaming: per bullet → store.update_partial(...)
        (terminal)      → store.complete(research_id, summary)

GET /api/research/{id}  (polled every 2s)
  └─ returns { status, summary, progress }

GET /api/facts          (fetched once, TanStack-cached)
  └─ returns { facts: [...] }
```

The progress bar fills 5 → 20 → 45 → 55 → 85 across nodes 1–4 and the start of the formatter. It never needs to reach 100%: the first streamed bullet retires the progress view. On `complete`, the trailer skeleton disappears.

## Components

### Backend: `store/research_store.py`

`ResearchTask` gains two fields:

```python
@dataclass
class ResearchTask:
    ...
    progress_pct: int = 0
    progress_label: str = "Getting started"
```

Two new methods on `InMemoryResearchStore`:

```python
async def update_progress(self, research_id: str, pct: int, label: str) -> None:
    async with self._lock:
        task = self._tasks.get(research_id)
        if not task:
            return
        task.progress_pct = pct
        task.progress_label = label
        if task.status == "pending":
            task.status = "in_progress"

async def update_partial(self, research_id: str, summary: PydanticBaseModel) -> None:
    """Replace the in-progress summary with a newer partial (streaming bullets).

    Sets status to in_progress if pending. Does NOT mark complete — the
    caller invokes complete() at the end (or fail() on error).
    """
    async with self._lock:
        task = self._tasks.get(research_id)
        if not task:
            return
        task.summary = summary
        if task.status == "pending":
            task.status = "in_progress"
```

`update_partial` is distinct from `complete_section()` (v1's per-section append shape). The v4 case is a whole-summary replace: the bullets list is small (6–8 items), so replacing it each tick is cheap and avoids any partial-state race for the polling reader.

### Backend: `research/overview/progress.py` (new)

Single source of truth for the step → label → percent mapping. The percentages are first-draft, informed by V4_PERFORMANCE latency notes (breadth/research_agent/formatter dominate); they are trivially tunable in this one list.

```python
from research.overview.state import V4State

# (node_key, label shown while running, percent shown while running)
PROGRESS_STEPS: list[tuple[str, str, int]] = [
    ("query_generator", "Planning what to research", 5),
    ("breadth_search",  "Searching the web",         20),
    ("filter",          "Sorting through sources",   45),
    ("research_agent",  "Digging into the details",  55),
    ("formatter",       "Writing the summary",        85),
]

_LOOKUP = {key: (label, pct) for key, label, pct in PROGRESS_STEPS}


async def report_step(state: V4State, key: str) -> None:
    """Report the current pipeline step to the store, if plumbed.

    No-ops when store/research_id are absent from state (e.g. unit tests
    invoking nodes directly), so nodes can call it unconditionally.
    """
    store = state.get("store")
    research_id = state.get("research_id")
    if store is None or research_id is None:
        return
    label, pct = _LOOKUP[key]
    await store.update_progress(research_id, pct, label)
```

Each of the five node functions calls `await report_step(state, "<key>")` as its first statement. Explicit calls (vs. a decorator) keep the reporting greppable and avoid wrapping concerns around node signatures.

### Backend: `research/overview/state.py`

Add two optional fields to `V4State` (consumed by `report_step` and by `_formatter_streaming`; other nodes ignore them):

```python
store: NotRequired[InMemoryResearchStore]
research_id: NotRequired[str]
```

### Backend: `research/overview/pipeline.py`

Populate the new state fields in `research_representative`:

```python
initial: V4State = {"rep": rep, "usage_log": []}
if store is not None and research_id is not None:
    initial["store"] = store
    initial["research_id"] = research_id
result = await pipeline_graph.ainvoke(initial, config={"run_name": f"v4:pipeline:{rep.name}"})
```

The terminal `await store.complete(research_id, summary)` stays. For streaming runs it is an idempotent confirmation of the summary already in the store; for non-streaming runs it remains the only write.

### Backend: `research/overview/nodes/formatter.py`

Per the formatter-streaming spec, split into a dispatch:

```python
@observe(name="v4-formatter")
async def formatter(state: V4State) -> dict:
    await report_step(state, "formatter")
    if _streaming_enabled():
        return await _formatter_streaming(state)
    return await _formatter_structured(state)
```

- `_formatter_structured()` — today's `with_structured_output` body lifted as-is (the fallback path).
- `_formatter_streaming()` — NDJSON line stream (`{"text":"...","sources":["url",...]}` one object per line). Maintains a line buffer; on each completed line parses JSON, builds `Citation`s + `[N]` markers in Python (URLs not in the breadth/depth pool dropped silently with a log, matching `_build_citations`), appends the bullet, and `await store.update_partial(...)`. End-of-stream: drain the buffer; if `len(bullets) < MIN_BULLETS` raise `RuntimeError` (→ pipeline returns `(None, total)` → router `store.fail()` → frontend failure UI).

Gating helpers:

```python
def _streaming_enabled() -> bool:
    return os.getenv("OVERVIEW_V4_FORMATTER_STREAMING", "true").strip().lower() in ("1", "true", "yes", "on")

def _min_bullets() -> int:
    return int(os.getenv("OVERVIEW_V4_FORMATTER_MIN_BULLETS", "3"))
```

**Delta from the formatter-streaming spec:** that spec defaulted `OVERVIEW_V4_FORMATTER_STREAMING=false` for a cautious prod rollout. Here it defaults **`true`** — streaming is the experience being built. The env flag and the structured-output path remain as a one-flip escape hatch.

See the formatter-streaming spec for the full `_handle_line` logic, chunk-buffering details, `formatter_user_streaming.txt` prompt contents, and per-line error handling. This spec does not restate them.

### Backend: `research/overview/prompts/formatter_user_streaming.txt` (new)

Per the formatter-streaming spec: a copy of `formatter_user.txt` with the trailing wire-shape reminder rewritten for the NDJSON one-object-per-line shape (`text` + `sources` keys, no outer array, no `[N]` markers — the system appends those).

### Backend: `routers/overview.py`

```python
class ProgressInfo(BaseModel):
    pct: int
    label: str

class ResearchResponse(BaseModel):
    research_id: str
    status: str
    summary: ResearchSummary | None = None
    progress: ProgressInfo | None = None
```

`get_research` populates `progress` from the task when `status` is `pending`/`in_progress`:

```python
progress = None
if task.status in ("pending", "in_progress"):
    progress = ProgressInfo(pct=task.progress_pct, label=task.progress_label)
return ResearchResponse(
    research_id=task.research_id,
    status=task.status,
    summary=task.summary,
    progress=progress,
)
```

### Backend: `db.py`

```python
async def get_civics_facts() -> list[str]:
    pool = await get_pool()
    rows = await pool.fetch("SELECT text FROM facts WHERE active ORDER BY id")
    return [r["text"] for r in rows]
```

Small result set; no caching needed server-side (the frontend caches it for the session).

### Backend: `routers/facts.py` (new)

```python
from fastapi import APIRouter
from pydantic import BaseModel
from db import get_civics_facts

router = APIRouter()

class FactsResponse(BaseModel):
    facts: list[str]

@router.get("/api/facts")
async def get_facts() -> FactsResponse:
    return FactsResponse(facts=await get_civics_facts())
```

Registered in `main.py` alongside the other routers. No rate limit — the payload is tiny and cacheable.

### Backend: `schema.sql`

New table + seed:

```sql
CREATE TABLE facts (
    id          SERIAL PRIMARY KEY,
    text        TEXT NOT NULL,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO facts (text) VALUES
  ('...'),  -- ~15–20 starter civics/America facts authored during implementation
  ...;
```

Because `schema.sql` is "apply once to a fresh DB" (no migration history), the implementation will also produce the standalone `CREATE TABLE` + `INSERT` statements to run once against the existing prod database.

### Frontend: `types/index.ts`

```ts
export interface ProgressInfo {
  pct: number;
  label: string;
}

export interface ResearchResponse {
  research_id: string;
  status: string;
  summary: ResearchSummary | null;
  progress?: ProgressInfo | null;
}
```

### Frontend: `hooks/useResearchQuery.ts`

`ResearchEntry` gains `progress: ProgressInfo | null`. The poll loop already calls `setEntry` on each in-progress tick; it additionally reads `data.progress` and stores it. Add a `getProgress(rep)` accessor mirroring `getStatus`/`getSummary`. No change to the polling cadence or cache-key scheme.

### Frontend: `hooks/useFactsQuery.ts` (new)

```ts
export function useFactsQuery() {
  return useQuery({
    queryKey: ["facts"],
    queryFn: async (): Promise<string[]> => {
      const resp = await fetch(`${API_URL}/api/facts`);
      if (!resp.ok) return [];
      const data = await resp.json();
      return data.facts ?? [];
    },
    staleTime: Infinity,        // facts don't change within a session
  });
}
```

Optionally prefetched on the results layout mount so facts are ready before the first research click.

### Frontend: `components/overview/ResearchProgress.tsx` (new)

Presentational. Takes `{ pct, label }` (falls back to `0 / "Getting started"` if progress is null on the first tick). Renders a filling bar, the percentage, and the current label.

### Frontend: `components/overview/FactsCarousel.tsx` (new)

Self-contained, no props. Calls `useFactsQuery()`, rotates through facts on a ~6s timer starting at a random index, simple fade. While facts are still loading/empty it renders nothing (the progress bar alone carries the loading state).

### Frontend: rendering gate

In the bullets `ResearchContent` (and/or its parent loading branch), implement the gate from the table above. The loading branch (`status === "loading" && bullets.length === 0`) renders `<ResearchProgress>` + `<FactsCarousel>` in place of today's skeleton. The streaming branch (`bullets.length > 0`) renders the bullets plus a trailer skeleton while still loading, per the formatter-streaming spec.

### Frontend: `RepCard.tsx`, `CandidateCard.tsx`

Add `getProgress(rep)` and pass progress into the loading branch. **Remove the existing "Scraping the web…" message** — the live progress label now owns the loading voice.

## Data flow (streaming run)

```
t=0     POST /api/research → task created (pending, progress 0/"Getting started")
t=0     Pipeline starts; query_generator reports 5% "Planning what to research"
t=~1s   breadth_search reports 20% "Searching the web"
t=~Xs   filter reports 45% "Sorting through sources"
t=~Xs   research_agent reports 55% "Digging into the details"
        (frontend polls every 2s; bar + label advance; facts rotating throughout)
t=~Ns   formatter reports 85% "Writing the summary"; begins NDJSON stream
t=~N+s  first line parsed → store.update_partial(bullets=[b1], ...)
        → next poll: bullets.length === 1 → frontend flips to bullets view
        → progress bar retired; trailer skeleton shown
... bullets accumulate ...
t=end   stream done → store.complete(...) → next poll: status complete → trailer gone
```

## Error handling

| Failure mode | Detection | Outcome |
|---|---|---|
| Cache hit | router pre-check | `complete` returned immediately; progress/facts never shown |
| First poll before any node reports | progress is `0/"Getting started"` | progress bar at 0, facts already rotating |
| Node raises mid-pipeline | pipeline `try/except` → `store.fail()` | failure UI replaces progress/facts |
| Facts endpoint fails / empty | `useFactsQuery` returns `[]` | carousel renders nothing; progress bar unaffected |
| Streaming < `MIN_BULLETS` valid bullets | end-of-stream check | `RuntimeError` → `store.fail()` → failure UI |
| Single malformed/hallucinated line | per-line parse/pool check | logged + skipped; stream continues (per streaming spec) |

The graph is linear (`query_generator → breadth_search → filter → research_agent → formatter`), so progress is monotonic — no out-of-order completion to reconcile.

## Testing

**Backend unit:**
- `update_progress` sets `progress_pct`/`progress_label` and transitions `pending → in_progress`.
- `report_step` no-ops when `store`/`research_id` are absent from state; writes the right label/pct when present.
- `get_civics_facts` returns only `active` rows, ordered.
- Formatter streaming tests per the streaming spec: `_handle_line` parse/skip/dedupe/drop-unknown-url, chunk buffering, min-bullets threshold, dispatch picks streaming vs. structured by env flag.

**Backend integration:**
- Run the `formatter` node against a recorded chunk fixture; assert the store sees monotonically growing partial writes and the final summary matches the all-at-once expectation.

**Frontend (manual dev smoke):**
- Progress bar fills across nodes with advancing labels; facts rotate.
- First streamed bullet retires the progress view; trailer skeleton shows while streaming, gone on complete.
- Failure path shows the error state, not a stuck bar.
- Facts endpoint empty → carousel absent, progress bar still works.

## Rollout

Feature branch (`formatter-streaming`) — low risk, so streaming defaults on from the start. Sequence:

1. Land backend progress reporting + facts table/endpoint + formatter streaming. Apply the facts table + seed to the dev DB.
2. Land frontend progress component, facts carousel, hook changes, rendering gate.
3. Dev smoke test end-to-end on a few reps; tune the `PROGRESS_STEPS` percentages against observed node timings.
4. Apply the facts table + seed to prod DB before/with deploy.
5. Update `CLAUDE.md` (new env vars, facts table, `/api/facts`) and mark the formatter-streaming `[L]` item in `V4_PERFORMANCE.md` with a postmortem.

The structured-output formatter path stays in the codebase as the `OVERVIEW_V4_FORMATTER_STREAMING=false` escape hatch.

## Files touched

- `backend/store/research_store.py` — progress fields, `update_progress()`, `update_partial()`
- `backend/research/overview/progress.py` — **new** (step registry + `report_step`)
- `backend/research/overview/state.py` — `store` + `research_id` on `V4State`
- `backend/research/overview/pipeline.py` — populate them in the initial state
- `backend/research/overview/nodes/query_generator.py`, `breadth_search.py`, `filter_node.py`, `research_agent.py` — `report_step` call at node entry
- `backend/research/overview/nodes/formatter.py` — streaming/structured split + `report_step`
- `backend/research/overview/prompts/formatter_user_streaming.txt` — **new**
- `backend/routers/overview.py` — `ProgressInfo`, `progress` on `ResearchResponse`
- `backend/routers/facts.py` — **new** (`GET /api/facts`)
- `backend/main.py` — register facts router
- `backend/db.py` — `get_civics_facts()`
- `backend/schema.sql` — `facts` table + seed
- `frontend/src/hooks/useResearchQuery.ts` — `progress` in entry + `getProgress`
- `frontend/src/hooks/useFactsQuery.ts` — **new**
- `frontend/src/types/index.ts` — `ProgressInfo` + `progress` on `ResearchResponse`
- `frontend/src/components/overview/ResearchProgress.tsx` — **new**
- `frontend/src/components/overview/FactsCarousel.tsx` — **new**
- `frontend/src/components/overview/bullets/*` — rendering gate (progress+facts vs. streaming bullets vs. complete)
- `frontend/src/components/RepCard.tsx`, `CandidateCard.tsx` — pass `getProgress`, drop "Scraping the web…"
- `CLAUDE.md` — `OVERVIEW_V4_FORMATTER_STREAMING` / `OVERVIEW_V4_FORMATTER_MIN_BULLETS` env vars, `facts` table, `/api/facts` endpoint
- `docs/initiatives/V4_PERFORMANCE.md` — mark the formatter streaming `[L]` item with a postmortem

## Open implementation questions

- **`PROGRESS_STEPS` percentages** are first-draft guesses; calibrate against observed per-node timings during dev smoke testing (step 3).
- **`chunk.content` shape** on a LangChain `AIMessageChunk` is `str | list` — coerce defensively (per the formatter-streaming spec's open question).
- **Facts prefetch** — whether to prefetch `/api/facts` on results-layout mount or lazily on first carousel render. Default to prefetch for a ready-on-first-click experience; decide during implementation.
