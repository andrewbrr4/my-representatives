# Kill SSE, Switch to POST + Poll

**Date:** 2026-03-15
**Status:** Proposed

## Problem

The SSE streaming connection between frontend and backend is brittle. The frontend uses `fetch()` + `ReadableStream` (not native `EventSource`), which lacks automatic reconnection. Infrastructure (Cloud Run, proxies) kills idle SSE connections during long research gaps. When the connection drops, backend research keeps running (incurring API costs) but results don't reach the user.

A polling fallback exists but is secondary — the SSE path is primary and fragile.

## Decision

Remove SSE entirely. Make `POST /api/representatives` a plain JSON endpoint. Use the existing `GET /api/jobs/{job_id}` polling endpoint as the sole mechanism for delivering research results.

## Design

### Backend

**`POST /api/representatives`** (modified):

1. Receives `AddressRequest`, validates address
2. Runs rep lookup concurrently (Census Geocoder + Congress API, Cicero API) — same logic as today
3. Sorts reps by level priority (federal > state > municipal)
4. Creates job in `JobStore` via `job_store.create_job(job_id, reps)`
5. Spawns `_run_all_research(job_id, reps)` as `asyncio.create_task` (fire-and-forget)
6. Returns plain JSON: `{ "job_id": string, "representatives": Representative[] }`

Response model:

```python
class LookupResponse(BaseModel):
    job_id: str
    representatives: list[Representative]
```

**`GET /api/jobs/{job_id}`** — unchanged. Returns `JobStatusResponse` with per-rep research status/summaries and overall job status.

**Removals:**
- `sse-starlette` removed from dependencies
- `EventSourceResponse` import and `event_stream()` generator deleted from `representatives.py`
- All SSE event yielding logic removed

**Unchanged:**
- `_run_all_research()` and `_research_rep_to_store()` — same fire-and-forget pattern
- `JobStore` and `RepCache` — no changes
- Research pipeline — no changes
- `routers/jobs.py` — no changes

### Frontend

**`useRepresentatives.ts`** (rewritten):

1. `lookup(address)` calls `POST /api/representatives` via plain `fetch`, parses JSON
2. Sets representatives immediately (without summaries)
3. Starts polling `GET /api/jobs/{job_id}` every 2s
4. Each poll: iterate `job.research`, find entries with `status === "complete"` or `"failed"` not yet delivered (tracked via `deliveredRef`), update the corresponding rep's summary in state
5. When `job.status === "done"` or `"error"`: stop polling, set `loading = false`
6. `useEffect` cleanup stops polling on component unmount

**Public API unchanged:** `{ representatives, loading, error, lookup }` — no component changes needed.

**Removed:**
- `ReadableStream` / `reader.read()` loop
- SSE line parsing (`buffer.split("\n")`, `event:` / `data:` prefix handling)
- `handleSSEEvent()` function
- `receivedDone` flag and SSE-to-polling fallback logic

**Kept:**
- `abortRef` — cancels in-flight fetch on new search
- `deliveredRef` — avoids re-rendering already-delivered research
- `pollTimerRef` / `startPolling` / `stopPolling` — become the primary (only) mechanism

### Error handling

- If the POST fails (network error, 4xx, 5xx): set error message, stop loading. No job was created, nothing to poll.
- If polling gets a 404: job expired, show "Session expired. Please search again." and stop loading. (Same as current behavior.)
- If polling gets a network error: silently retry on next interval. (Same as current behavior.)
- If `job.status === "error"`: show `error_detail` from job, stop polling.

## Not in scope

- **Rep cache investigation** — the `RepCache` may not be working correctly; will investigate separately.
- **Job cancellation** — no mechanism to cancel backend research when user navigates away. Follow-up feature.
- **Polling optimization** — no exponential backoff or `?since=` parameter. Payload size is fine for current scale.

## Migration

This is a breaking change to the API contract (`POST /api/representatives` returns JSON instead of SSE). Since there are no external consumers, no migration path is needed — update backend and frontend together.
