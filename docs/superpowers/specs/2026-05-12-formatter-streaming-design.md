# Formatter Streaming Design

**Status:** Spec — pending implementation
**Initiative:** [V4_PERFORMANCE.md](../../initiatives/V4_PERFORMANCE.md) — open `[L]` formatter idea
**Pipeline:** v4 rep overview, `formatter` node only

## Goal

Stream the v4 formatter's bullet output so the user sees the first bullet in ~5–8s instead of waiting ~22s for the full block. Perceived-latency win with no quality cost (model + prompt unchanged).

## Non-goals

- No change to `query_generator`, `breadth_search`, `filter`, or `research_agent` nodes.
- No change to non-v4 pipelines (legacy v1/v2/v3) or non-rep pipelines (elections, issues).
- No model swap. Sonnet stays — the all-Haiku experiment shelved that lever.
- No new transport. Existing 2s polling against `InMemoryResearchStore` carries the partials.
- No structured-output schema for the streaming path. Switching to NDJSON is the whole point.
- No change to Pydantic `ResearchSummary` shape. Same `bullets` / `citations` / `sources` fields the frontend already renders.

## High-level approach

Replace the formatter's `with_structured_output` call with **NDJSON line streaming** (one JSON object per line: `{"text":"...","sources":["url",...]}`). Backend parses each completed line, builds citations + `[N]` markers incrementally, and writes the growing summary to the store on every new bullet. Existing 2s frontend poll picks up partials.

Gated behind `OVERVIEW_V4_FORMATTER_STREAMING` env var (default `false`). Structured-output path stays intact as the fallback so revert is one env-var flip.

## Architecture

```
formatter node
├─ branch: streaming env flag
│   ├─ ON  → _formatter_streaming() — NDJSON line stream + per-bullet store updates
│   └─ OFF → _formatter_structured() — existing with_structured_output + retry path
└─ shared helpers: _format_breadth_block, _format_depth_block, _build_sources,
                    _show_sources_enabled, _model_id, citation/marker logic
```

Both branches return `{"summary": ResearchSummary, "usage_log": [stats]}`. The streaming branch additionally writes partials to the store via a new `store.update_partial()` method as bullets land. The non-streaming branch behaves exactly as today.

## Components

### Backend: `research/overview/nodes/formatter.py`

Top-level `formatter()` becomes a thin dispatch:

```python
@observe(name="v4-formatter")
async def formatter(state: V4State) -> dict:
    if _streaming_enabled():
        return await _formatter_streaming(state)
    return await _formatter_structured(state)
```

`_formatter_structured()` is the current code body, lifted as-is. Shared helpers stay at module level so both branches use the same prompt loading, citation building, and source assembly.

`_formatter_streaming()` does:

1. Load prompts (same files as today). Append a small NDJSON-shape addendum to the user prompt — `formatter_user_streaming.txt` with examples of the `{"text":"...","sources":[...]}` per-line wire shape and an explicit "no outer array, no commentary, one object per line" instruction.
2. Build `pool_by_url: dict[str, SearchResult]` from `filtered + depth` for citation lookups.
3. Compute `sources` once via `_build_sources()` if `_show_sources_enabled()`.
4. Open the stream: `async for chunk in model.astream([SystemMessage, HumanMessage], config=...)`.
5. Maintain `line_buffer: str`, `bullets: list[str]`, `citations: list[Citation]`, `url_to_n: dict[str, int]`.
6. On each chunk: append `chunk.content` (or string-coerce it) to `line_buffer`; while `\n` in buffer, split off the line and call `_handle_line(line)`.
7. After stream ends: drain `line_buffer` (in case the model didn't terminate with `\n`) — one final `_handle_line` if non-empty.
8. If `len(bullets) < MIN_BULLETS`: raise `RuntimeError("formatter produced too few valid bullets")`. The pipeline-level `try/except` in `pipeline.py:research_representative` catches this, returns `(None, total)`, the router calls `store.fail(research_id)`, and the frontend's existing failure UI fires.
9. Build the final `ResearchSummary` and return.

`_handle_line(line, …)`:

- Strip whitespace; skip if empty.
- `try: obj = json.loads(line)` — `JSONDecodeError` → log warning + skip.
- Validate: `obj` must be a dict with `text: str` (non-empty after strip) and `sources: list[str]`. Bad shape → log + skip.
- For each URL in `sources` (preserving order): if not already in `url_to_n` and present in `pool_by_url`, append a `Citation(title, url, published_date)` and assign `url_to_n[url] = len(citations)`. URLs not in pool dropped silently with a single warning log per URL (matches existing `_build_citations` philosophy).
- Compute `marker = "".join(f"[{n}]" for n in sorted({url_to_n[u] for u in sources if u in url_to_n}))`.
- Append `f"{text} {marker}".rstrip()` (or bare text if no marker) to `bullets`.
- `await store.update_partial(research_id, ResearchSummary(bullets=bullets, citations=citations, sources=sources))`.

Module-level constants:

```python
def _streaming_enabled() -> bool:
    return os.getenv("OVERVIEW_V4_FORMATTER_STREAMING", "").strip().lower() in ("1", "true", "yes", "on")

def _min_bullets() -> int:
    return int(os.getenv("OVERVIEW_V4_FORMATTER_MIN_BULLETS", "3"))
```

### Backend: `research/overview/state.py`

Add two optional fields to `V4State`:

```python
store: NotRequired[InMemoryResearchStore]
research_id: NotRequired[str]
```

These are populated in the initial state by `pipeline.py:research_representative` and consumed only by `_formatter_streaming`. Other nodes ignore them.

### Backend: `research/overview/pipeline.py`

`research_representative()` becomes:

```python
initial: V4State = {"rep": rep, "usage_log": []}
if store is not None and research_id is not None:
    initial["store"] = store
    initial["research_id"] = research_id
result = await pipeline_graph.ainvoke(initial, ...)
```

The terminal `await store.complete(research_id, summary)` call stays unchanged. For streaming runs it's a redundant-but-idempotent confirmation of the same summary already in the store; for non-streaming runs it's the only write.

### Backend: `store/research_store.py`

New method on `InMemoryResearchStore`:

```python
async def update_partial(self, research_id: str, summary: PydanticBaseModel) -> None:
    """Replace the in-progress summary with a newer partial.

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

Distinct from `complete_section()`, which is for v1's per-section streaming pattern (different shape: appends one section + one citation list per call). The v4 streaming case is "whole-summary replace" — bullets list is small (6–8 items), replacing it on each tick is cheaper than mutating it in place and avoids any partial-state race for the polling reader.

### Backend: `research/overview/prompts/formatter_user_streaming.txt`

Copy of `formatter_user.txt` with the trailing wire-shape reminder rewritten:

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

The system prompt (`formatter_system.txt`) is unchanged. All bucket taxonomy, importance-pruning, bullet count (6–8), word count (~14–22), no-identity-framing rules, and the date-tagging rule continue to apply.

### Frontend: `frontend/src/components/overview/bullets/ResearchContent.tsx`

Today the gate is binary: `bullets.length === 0` → skeleton, otherwise render bullets. Streaming changes this to a tri-state, but only if we know the request is still loading. Since `ResearchContent` doesn't currently take a status prop, add one:

```tsx
export function ResearchContent({
  summary,
  status,
}: {
  summary: BulletsResearchSummary;
  status?: "loading" | "complete" | "failed";
}) {
  const { bullets, citations, sources } = summary;

  if (bullets.length === 0) {
    return <BulletsSkeleton />;  // unchanged: full skeleton when nothing yet
  }

  return (
    <div className="...">
      <ul className="...">{bullets.map(...)}</ul>
      {status === "loading" && <BulletsTrailerSkeleton />}
      <FurtherReading sources={sources} />
    </div>
  );
}
```

`BulletsTrailerSkeleton` is a 2-row variant of the existing `BulletsSkeleton` — same widths, smaller height, just enough to signal "more coming." Disappears the instant `status === "complete"`.

Callers (`RepCard`, `CandidateCard`) already know the status from `useResearchQuery().getStatus(rep)` and pass it through. No new state plumbing needed.

`FurtherReading` already handles empty `sources` (renders nothing), so populating it on the first partial write is naturally a no-op until sources land.

### Frontend: `useResearchQuery.ts`

No change. The polling loop already calls `setEntry` on every poll where `data.summary` is present, regardless of which fields changed. New bullets in the summary just update the cache and trigger a re-render.

## Data flow (streaming run)

```
t=0     POST /api/research → router creates task (status=pending, summary=ResearchSummary())
t=0     Pipeline starts: query_gen → breadth → filter → research_agent → formatter
t=~28s  Formatter starts streaming (replaces ~22s blocking call)
t=~33s  First newline lands → _handle_line parses {"text":"...","sources":[...]}
        → store.update_partial(summary={bullets:[bullet1], citations:[...], sources:[...]})
        → task.status = "in_progress"
t=~33s  Frontend's next 2s poll → ResearchResponse(status="in_progress", summary=…)
        → bullets.length === 1 → render bullet1 + trailer skeleton + Further Reading
t=~35s  Second bullet lands → store.update_partial → next poll picks it up
... repeats ...
t=~38s  Stream ends → final summary returned
        → pipeline.research_representative calls store.complete(...)
        → next poll → status="complete" → trailer skeleton disappears
```

The exact numbers depend on Sonnet's first-bullet latency under streaming, which we'll measure once shipped (Langfuse spans, see Observability below).

## Error handling

| Failure mode | Detection | Outcome |
|---|---|---|
| Single line malformed JSON | `json.loads` raises | Logged + skipped; continue stream |
| Single line wrong shape | type/key check fails | Logged + skipped; continue stream |
| URL cited but not in pool | `url not in pool_by_url` | Dropped silently with log; bullet renders with one fewer marker (existing behavior) |
| Stream completes with < `MIN_BULLETS` bullets | end-of-stream check | Raise `RuntimeError` → pipeline returns `(None, total)` → router calls `store.fail()` → frontend shows "Research unavailable" + Retry |
| LLM call itself raises (network, rate limit) | exception in `astream` | Propagates to pipeline-level `try/except` → same fail path |
| Store call raises (shouldn't happen — in-memory) | exception in `update_partial` | Propagates → fail path |

The min-bullet threshold is the only new failure mode. It exists because we lose the schema validation that `with_structured_output` provided. Pegging at 3 (out of a 6–8 target) is intentionally lenient — if the formatter occasionally emits 4–5 valid bullets when one or two lines were malformed, we'd rather show those than fail the whole run. Tunable via `OVERVIEW_V4_FORMATTER_MIN_BULLETS`.

The structured-output path keeps its `with_retry(retry_if_exception_type=ValidationError, stop_after_attempt=2)` and `_zip_bullets` length-mismatch tolerance, so flipping the env var off restores the existing safety net immediately.

## Observability

- The `@observe(name="v4-formatter")` decorator stays on the dispatching `formatter()`, so traces continue to span the whole node regardless of branch.
- `UsageTracker()` callback works identically with `astream` — same `config={"callbacks":[…]}` pattern.
- Add a single info log at end-of-stream: `f"[v4] Formatter streamed {len(bullets)} bullets in {n_chunks} chunks; dropped {n_malformed} malformed lines, {n_hallucinated} unknown URLs"`. Same monitoring posture as the existing structured-output path.

## Testing

**Backend unit tests** — `backend/tests/test_formatter_streaming.py` (new file):

- `test_handle_line_parses_valid_object` — happy path, single well-formed line.
- `test_handle_line_skips_blank_and_malformed` — empty string, malformed JSON, wrong-shape dict, all skipped without raising.
- `test_handle_line_drops_unknown_urls` — URL not in pool → dropped from citations, marker reflects only valid ones.
- `test_handle_line_dedupes_urls_across_bullets` — URL cited in bullet 2 that already appeared in bullet 1 reuses the same N.
- `test_chunk_buffering` — feed chunks split mid-line; ensure lines are reassembled correctly.
- `test_min_bullets_threshold` — feed a stream that yields fewer than `MIN_BULLETS` valid bullets; expect `RuntimeError`.
- `test_streaming_disabled_uses_structured` — env var off → `_formatter_structured` is called (mock both branches, assert which fires).

**Backend integration test** — `test_formatter_streaming_e2e.py`:

- Build a fake `ChatAnthropic` (or monkey-patch `astream`) that yields a recorded sequence of chunks reproducing a real Sonnet stream (saved as a fixture from a manual run). Run the whole `formatter` node against a fixture `V4State`. Assert the in-memory store sees N partial writes, each with monotonically growing `bullets`, and the final summary matches the all-bullets-at-once expected output.

**Frontend** — manual smoke test on dev (per CLAUDE.md, "for UI or frontend changes, start the dev server and use the feature in a browser before reporting the task as complete"). Verify:
- First bullet appears in <10s on a real rep run.
- Trailer skeleton visible while streaming, gone on complete.
- Further Reading list appears with the first bullet.
- Failure path (force `OVERVIEW_V4_FORMATTER_MIN_BULLETS=99`) shows "Research unavailable" + Retry, not stuck-skeleton.
- `OVERVIEW_V4_FORMATTER_STREAMING=false` still works exactly as today.

## Rollout

1. Land code with `OVERVIEW_V4_FORMATTER_STREAMING` defaulting to `false`. CI green, structured path verified unchanged.
2. Flip to `true` in dev, run a handful of reps, eyeball traces in Langfuse for: end-to-end latency reduction, bullet count parity (~6–8), citation count parity, malformed-line counts.
3. If clean, flip to `true` in prod via Cloud Run env var. Watch traces + error logs for 24h.
4. After ~a week of clean prod data, change the code default to `true` and remove the feature flag in a follow-up commit (or keep it as a long-term escape hatch — decide based on operational comfort).

The structured-output code path stays in the codebase through step 4 at minimum. After removal it lives in git history if we ever need to revert.

## Files touched

- `backend/research/overview/nodes/formatter.py` — split into `_formatter_streaming` + `_formatter_structured`, add dispatch, helpers stay shared.
- `backend/research/overview/state.py` — add `store` + `research_id` to `V4State`.
- `backend/research/overview/pipeline.py` — populate the new state fields.
- `backend/research/overview/prompts/formatter_user_streaming.txt` — new file (NDJSON shape reminder).
- `backend/store/research_store.py` — add `update_partial()`.
- `backend/tests/test_formatter_streaming.py` — new test file.
- `frontend/src/components/overview/bullets/ResearchContent.tsx` — accept `status` prop, render trailer skeleton when streaming.
- `frontend/src/components/RepCard.tsx`, `CandidateCard.tsx` — pass `status` into `ResearchContent`.
- `CLAUDE.md` — add `OVERVIEW_V4_FORMATTER_STREAMING` + `OVERVIEW_V4_FORMATTER_MIN_BULLETS` to env-var section; brief note in the v4 formatter description that streaming is the new default path (once flipped).
- `docs/initiatives/V4_PERFORMANCE.md` — once shipped, mark the formatter streaming `[L]` item as `[x]` with a one-paragraph postmortem (latency before/after, any quality observations, rollout notes).

## Open implementation questions

- **Where does `chunk.content` live on a LangChain `AIMessageChunk`?** It's a string for ChatAnthropic but the typing is `str | list`. Coerce defensively (`if isinstance(content, str)`). Resolve at implementation time by inspecting the actual chunk type.
- **Cloud Run buffering:** SSE-style streams sometimes hit reverse-proxy buffering on Cloud Run. We're not using SSE — partials reach the frontend via the polling endpoint, which returns a complete JSON response each time — so this isn't a risk for this design. Worth noting if we ever swap to SSE later.
