# Loading Progress + Fun Facts Design

**Status:** Spec — pending implementation
**Branch:** `formatter-streaming`
**Pipeline:** v4 rep overview (the production default at `research/overview/`)

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

2. **Bullet streaming at the formatter.** Replace the formatter's blocking `with_structured_output` call with NDJSON line streaming (one JSON object per line: `{"text":"...","sources":["url",...]}`), defaulted **on**. As each line is parsed, citations and `[N]` markers are built in Python and the growing summary is written to the store via `update_partial()`; the poll picks it up. The first bullet flips the frontend from the progress+facts view to the live bullets view.

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

The current `formatter()` body (the `with_structured_output` + `with_retry` call, `_FormatterOutput`, `_zip_bullets`, `_build_citations`, `_attach_markers`, `_build_sources`, `_format_breadth_block`, `_format_depth_block`, `_show_sources_enabled`, `_dedupe_depth_against_breadth`, `_model_id`) stays. The top-level `formatter()` becomes a thin dispatch and the existing body is lifted verbatim into `_formatter_structured()`:

```python
@observe(name="v4-formatter")
async def formatter(state: V4State) -> dict:
    await report_step(state, "formatter")
    if _streaming_enabled():
        return await _formatter_streaming(state)
    return await _formatter_structured(state)
```

All the existing module-level helpers stay shared between the two branches (same prompt loading, breadth/depth block formatting, citation building, source assembly). Both branches return `{"summary": ResearchSummary, "usage_log": [stats]}`.

**`_formatter_streaming(state)`** does:

1. Resolve `rep`, `filtered`, `depth`, `show_sources` exactly as `_formatter_structured` does (including the `_dedupe_depth_against_breadth` step when show-sources is on). Compute `breadth_block` / `depth_block` via the same helpers.
2. Build `pool_by_url: dict[str, SearchResult]` from `filtered + depth` for citation lookups, and compute `sources` once via `_build_sources()` if `_show_sources_enabled()`.
3. Load `formatter_system.txt` (unchanged) and the new `formatter_user_streaming.txt`, substituting the same template vars.
4. Open the stream: `async for chunk in model.astream([SystemMessage, HumanMessage], config={"callbacks": [langfuse_handler, usage_tracker], "run_name": f"v4:formatter:{rep.name}"})`. No `with_structured_output` — raw text chunks.
5. Maintain `line_buffer: str`, `bullets: list[str]`, `citations: list[Citation]`, `url_to_n: dict[str, int]`. On each chunk, append `chunk.content` (string-coerce defensively — see open questions) to `line_buffer`; while `"\n" in line_buffer`, split off the line and call `_handle_line(...)`.
6. After the stream ends, drain `line_buffer` (model may not terminate with `\n`): one final `_handle_line` if non-empty.
7. If `len(bullets) < _min_bullets()`: raise `RuntimeError("formatter produced too few valid bullets")` → caught by `pipeline.py`'s `try/except` → returns `(None, total)` → router calls `store.fail()` → frontend failure UI.
8. Build the final `ResearchSummary(bullets=bullets, citations=citations, sources=sources)` and return `{"summary": summary, "usage_log": [usage_tracker.stats]}`.

**`_handle_line(line, *, pool_by_url, bullets, citations, url_to_n, research_id, store)`** (the per-line parser; mutates the running lists and writes a partial):

- Strip whitespace; skip if empty.
- `try: obj = json.loads(line)` — `JSONDecodeError` → log warning + skip (continue stream).
- Validate shape: `obj` must be a dict with `text: str` (non-empty after strip) and `sources: list[str]`. Bad shape → log + skip.
- For each URL in `sources` (preserving order): if not already in `url_to_n` and present in `pool_by_url`, append a `Citation(title, url, published_date)` and set `url_to_n[url] = len(citations)` (1-indexed N). URLs not in the pool are dropped silently with one warning log per URL — matching the existing `_build_citations` hallucination-drop philosophy.
- Compute `marker = "".join(f"[{n}]" for n in sorted({url_to_n[u] for u in sources if u in url_to_n}))`.
- Append `f"{text} {marker}".rstrip()` (or bare `text` if no marker) to `bullets`.
- `await store.update_partial(research_id, ResearchSummary(bullets=bullets, citations=citations, sources=sources))`.

This reuses the same citation/marker semantics as the structured path (`_build_citations` + `_attach_markers`), just applied incrementally per line instead of once over the full `pairs` list — so streaming and structured produce equivalent final output.

Gating helpers (module level):

```python
def _streaming_enabled() -> bool:
    return os.getenv("OVERVIEW_V4_FORMATTER_STREAMING", "true").strip().lower() in ("1", "true", "yes", "on")

def _min_bullets() -> int:
    return int(os.getenv("OVERVIEW_V4_FORMATTER_MIN_BULLETS", "3"))
```

**Default-on rationale:** streaming is the experience being built, so `OVERVIEW_V4_FORMATTER_STREAMING` defaults `true`. The env flag and the `_formatter_structured` path remain as a one-flip escape hatch; flipping it off restores today's `with_structured_output` + `with_retry` safety net and `_zip_bullets` length-tolerance immediately.

**Min-bullets threshold:** the only new failure mode. It exists because the streaming path loses the schema validation `with_structured_output` provided. Pegged at 3 (out of a 6–8 target) — intentionally lenient, so a run that emits 4–5 valid bullets after one or two malformed lines still shows the user something rather than failing. Tunable via `OVERVIEW_V4_FORMATTER_MIN_BULLETS`.

**Observability:** the `@observe(name="v4-formatter")` decorator stays on the dispatching `formatter()`, so traces span the whole node regardless of branch. `UsageTracker()` works identically with `astream` (same `config={"callbacks": […]}`). Add one end-of-stream info log: `f"[v4] Formatter streamed {len(bullets)} bullets in {n_chunks} chunks; dropped {n_malformed} malformed lines, {n_hallucinated} unknown URLs"`.

### Backend: `research/overview/prompts/formatter_user_streaming.txt` (new)

A copy of `formatter_user.txt` with the trailing wire-shape reminder rewritten for NDJSON. The system prompt (`formatter_system.txt`) is unchanged — all bucket taxonomy, importance-pruning, 6–8 bullet count, ~14–22 word count, no-identity-framing, and date-tagging rules continue to apply. The rewritten reminder:

> **OUTPUT FORMAT (CRITICAL):**
> Emit one bullet per line as a single JSON object on each line. No outer array, no markdown, no commentary, no leading/trailing text — just one JSON object per line, separated by `\n`.
>
> Wire shape per line:
>
> ```
> {"text": "Bullet content here.", "sources": ["https://example.com/a", "https://example.com/b"]}
> {"text": "Next bullet.", "sources": ["https://example.com/c"]}
> ```
>
> Rules:
> - Exactly one JSON object per line.
> - Keys are `text` (string) and `sources` (array of URL strings).
> - URLs in `sources` must be pulled from the breadth/depth blocks above. Do not invent URLs.
> - Do NOT emit `[N]` markers — the system appends them after parsing.

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

Presentational. Takes `progress?: ProgressInfo | null` and falls back to `{ pct: 0, label: "Getting started" }` when it's null on the first tick. Renders a filling bar, the percentage, and the current label.

### Frontend: `components/overview/FactsCarousel.tsx` (new)

Self-contained, no props. Calls `useFactsQuery()`, rotates through facts on a ~6s timer starting at a random index, simple fade. While facts are still loading/empty it renders nothing (the progress bar alone carries the loading state).

### Frontend: rendering gate

`ResearchContent` (the bullets renderer) takes a new optional `status?: "loading" | "complete" | "failed"` prop so it can distinguish "nothing yet" from "more coming":

```tsx
export function ResearchContent({ summary, progress, status }: {
  summary: BulletsResearchSummary;
  progress?: ProgressInfo | null;
  status?: "loading" | "complete" | "failed";
}) {
  const { bullets, citations, sources } = summary;

  if (bullets.length === 0) {
    return (
      <>
        <ResearchProgress progress={progress} />
        <FactsCarousel />
      </>
    );  // loading state: progress bar + facts, replaces today's skeleton
  }

  return (
    <div>
      <ul>{bullets.map(/* ... */)}</ul>
      {status === "loading" && <BulletsTrailerSkeleton />}
      <FurtherReading sources={sources} />
    </div>
  );
}
```

`BulletsTrailerSkeleton` is a 2-row variant of the existing bullets skeleton — same widths, shorter — that signals "more coming" while bullets are still streaming. It disappears the instant `status === "complete"`. `FurtherReading` already no-ops on empty `sources`, so it stays invisible until sources land. Callers (`RepCard`, `CandidateCard`) already hold the status; they pass `status` and `progress` through.

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
| Single malformed/hallucinated line | per-line parse/pool check | logged + skipped; stream continues |

The graph is linear (`query_generator → breadth_search → filter → research_agent → formatter`), so progress is monotonic — no out-of-order completion to reconcile.

## Testing

**Backend unit:**
- `update_progress` sets `progress_pct`/`progress_label` and transitions `pending → in_progress`.
- `report_step` no-ops when `store`/`research_id` are absent from state; writes the right label/pct when present.
- `get_civics_facts` returns only `active` rows, ordered.
- Formatter streaming tests: `_handle_line` parse/skip/dedupe/drop-unknown-url, chunk buffering (lines split across chunks reassembled correctly), min-bullets threshold raises, dispatch picks streaming vs. structured by env flag.

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
- **`chunk.content` shape** on a LangChain `AIMessageChunk` is typed `str | list` — for `ChatAnthropic` it's a string, but coerce defensively (`if isinstance(content, str)`). Confirm against the actual chunk type at implementation time.
- **Facts prefetch** — whether to prefetch `/api/facts` on results-layout mount or lazily on first carousel render. Default to prefetch for a ready-on-first-click experience; decide during implementation.
