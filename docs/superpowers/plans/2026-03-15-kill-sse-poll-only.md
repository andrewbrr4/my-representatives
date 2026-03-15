# Kill SSE, Switch to POST + Poll — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the brittle SSE streaming connection with a plain JSON POST + polling pattern for delivering research results to the frontend.

**Architecture:** `POST /api/representatives` becomes a synchronous JSON endpoint returning `{ job_id, representatives }`. Research runs as fire-and-forget background tasks writing to the in-memory `JobStore`. Frontend polls `GET /api/jobs/{job_id}` every 2s to pick up results.

**Tech Stack:** FastAPI, React, TypeScript

**Spec:** `docs/superpowers/specs/2026-03-15-kill-sse-poll-only-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `backend/models.py` | Add `LookupResponse` model |
| Modify | `backend/routers/representatives.py` | Replace SSE endpoint with JSON endpoint |
| Modify | `backend/requirements.txt` | Remove `sse_starlette` |
| Modify | `frontend/src/hooks/useRepresentatives.ts` | Rewrite: plain fetch + polling |
| Modify | `frontend/src/types/index.ts` | Add `LookupResponse` interface |

No new files. No changes to `routers/jobs.py`, `store/`, `research/`, `services/`, or any component files.

---

## Chunk 1: Backend Changes

### Task 1: Add `LookupResponse` model to `models.py`

**Files:**
- Modify: `backend/models.py:73-74` (insert after `RepresentativesResponse`)

- [ ] **Step 1: Add the new response model**

Add between `RepresentativesResponse` and `JobStatusResponse`:

```python
class LookupResponse(BaseModel):
    job_id: str
    representatives: list[Representative]
```

- [ ] **Step 2: Verify no type errors**

Run: `cd backend && python -c "from models import LookupResponse; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/models.py
git commit -m "feat: add LookupResponse model for JSON endpoint"
```

### Task 2: Rewrite `POST /api/representatives` as plain JSON endpoint

**Files:**
- Modify: `backend/routers/representatives.py`

- [ ] **Step 1: Replace the endpoint**

The full rewritten file should be:

```python
import asyncio
import json
import logging
import os
import uuid

from fastapi import APIRouter, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from models import AddressRequest, LookupResponse, Representative
from services.cicero import get_state_local_representatives
from services.congress import get_federal_representatives
from research.pipeline import research_representative
from store.dependencies import get_job_store, get_rep_cache

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


async def _research_rep_to_store(
    job_id: str, index: int, rep: Representative
) -> None:
    """Research a single rep, writing results to job store and rep cache."""
    job_store = get_job_store()
    rep_cache = get_rep_cache()
    try:
        summary = await research_representative(rep)
        await job_store.update_rep_research(job_id, index, summary, failed=summary is None)
        if summary is not None:
            await rep_cache.put(rep.name, rep.office, summary)
    except Exception as e:
        logger.warning(f"Research failed for {rep.name}: {e}")
        await job_store.update_rep_research(job_id, index, None, failed=True)


async def _run_all_research(job_id: str, reps: list[Representative], skip_cache: bool = False) -> None:
    """Fire-and-forget: research all reps and mark job done when finished."""
    job_store = get_job_store()
    rep_cache = get_rep_cache()

    tasks = []
    for i, rep in enumerate(reps):
        if not skip_cache:
            cached = await rep_cache.get(rep.name, rep.office)
            if cached is not None:
                await job_store.update_rep_research(job_id, i, cached)
                continue
        tasks.append(asyncio.create_task(_research_rep_to_store(job_id, i, rep)))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    await job_store.mark_done(job_id)
    logger.info(f"Job {job_id}: all research complete")


@router.post("/api/representatives")
@limiter.limit("10/minute")
async def lookup_representatives(
    request: Request,
    address_request: AddressRequest,
    fresh: bool = Query(False, description="Skip research cache and run fresh pipeline"),
) -> LookupResponse:
    if not address_request.address.strip():
        raise HTTPException(status_code=400, detail="Address is required.")

    skip_cache = fresh or os.getenv("DISABLE_REP_CACHE", "").lower() in ("true", "1")
    if skip_cache:
        logger.info("Research cache disabled for this request")

    logger.info(f"Looking up representatives for: {address_request.address}")

    # Phase 1: Look up all reps
    us_congress_reps_only = os.getenv("US_CONGRESS_REPS_ONLY", "").lower() in ("true", "1")
    try:
        if us_congress_reps_only:
            logger.info("US_CONGRESS_REPS_ONLY mode: skipping state/municipal lookup")
            reps = await get_federal_representatives(address_request.address)
        else:
            federal_reps, state_local_reps = await asyncio.gather(
                get_federal_representatives(address_request.address),
                get_state_local_representatives(address_request.address),
            )
            reps = federal_reps + state_local_reps
    except Exception as e:
        logger.error(f"Representative lookup error: {e}")
        raise HTTPException(
            status_code=502,
            detail="Could not look up representatives for that address. Please check the address and try again.",
        )

    if not reps:
        raise HTTPException(
            status_code=404,
            detail="No representatives found for that address.",
        )

    # Sort by level priority
    level_order = {"federal": 0, "state": 1, "municipal": 2}
    reps.sort(key=lambda r: level_order.get(r.level, 3))

    # Phase 2: Create job and spawn research
    job_id = uuid.uuid4().hex[:12]
    job_store = get_job_store()
    await job_store.create_job(job_id, reps)

    logger.info(f"Job {job_id}: starting research for {len(reps)} reps")
    asyncio.create_task(_run_all_research(job_id, reps, skip_cache=skip_cache))

    # Phase 3: Return reps + job_id as plain JSON
    return LookupResponse(job_id=job_id, representatives=reps)
```

Key changes from the current file:
- Removed `sse_starlette` import
- Removed `RepresentativesResponse` import, added `LookupResponse`
- Removed `json` import (no longer needed)
- Endpoint returns `LookupResponse` instead of `EventSourceResponse`
- No more `event_stream()` generator — the lookup, job creation, and research spawn happen directly in the endpoint
- Errors raise `HTTPException` instead of yielding SSE error events
- `_research_rep_to_store` and `_run_all_research` are completely unchanged

- [ ] **Step 2: Verify the import works**

Run: `cd backend && python -c "from routers.representatives import router; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/routers/representatives.py
git commit -m "feat: replace SSE endpoint with plain JSON POST"
```

### Task 3: Remove `sse_starlette` from dependencies

**Files:**
- Modify: `backend/requirements.txt:11`

- [ ] **Step 1: Remove the `sse_starlette` line**

Remove line 11 (`sse_starlette`) from `backend/requirements.txt`.

- [ ] **Step 2: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: remove sse_starlette dependency"
```

---

## Chunk 2: Frontend Changes

### Task 4: Add `LookupResponse` type to frontend

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add the interface**

Add after `RepresentativesResponse`:

```typescript
export interface LookupResponse {
  job_id: string;
  representatives: Representative[];
}
```

- [ ] **Step 2: Verify types compile**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: add LookupResponse type"
```

### Task 5: Rewrite `useRepresentatives` hook

**Files:**
- Modify: `frontend/src/hooks/useRepresentatives.ts`

- [ ] **Step 1: Rewrite the hook**

The full rewritten file:

```typescript
import { useState, useCallback, useRef, useEffect } from "react";
import type { Representative, LookupResponse, JobStatusResponse } from "@/types";

const API_URL = import.meta.env.VITE_API_URL || "https://my-reps-backend-968920716189.us-east1.run.app";
const POLL_INTERVAL_MS = 2000;

export function useRepresentatives() {
  const [representatives, setRepresentatives] = useState<Representative[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const deliveredRef = useRef<Set<number>>(new Set());

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  // Clean up polling on unmount
  useEffect(() => {
    return () => {
      stopPolling();
      abortRef.current?.abort();
    };
  }, [stopPolling]);

  const startPolling = useCallback((jobId: string) => {
    stopPolling();
    pollTimerRef.current = setInterval(async () => {
      try {
        const resp = await fetch(`${API_URL}/api/jobs/${jobId}`);
        if (resp.status === 404) {
          stopPolling();
          setError("Session expired. Please search again.");
          setLoading(false);
          return;
        }
        if (!resp.ok) return; // retry on next interval

        const job: JobStatusResponse = await resp.json();

        if (job.research) {
          for (const entry of job.research) {
            if (
              !deliveredRef.current.has(entry.index) &&
              (entry.status === "complete" || entry.status === "failed")
            ) {
              deliveredRef.current.add(entry.index);
              const summary = entry.summary;
              setRepresentatives((prev) => {
                const updated = [...prev];
                updated[entry.index] = { ...updated[entry.index], summary };
                return updated;
              });
            }
          }
        }

        if (job.status === "done" || job.status === "error") {
          stopPolling();
          if (job.status === "error" && job.error_detail) {
            setError(job.error_detail);
          }
          setLoading(false);
        }
      } catch {
        // Network error — keep polling
      }
    }, POLL_INTERVAL_MS);
  }, [stopPolling]);

  const lookup = useCallback(async (address: string) => {
    // Abort any in-flight request and stop existing polling
    abortRef.current?.abort();
    stopPolling();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);
    setRepresentatives([]);
    deliveredRef.current = new Set();

    try {
      const resp = await fetch(`${API_URL}/api/representatives`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address }),
        signal: controller.signal,
      });

      if (!resp.ok) {
        const data = await resp.json().catch(() => null);
        throw new Error(data?.detail || `Request failed (${resp.status})`);
      }

      const { job_id, representatives }: LookupResponse = await resp.json();

      // Set reps immediately (without summaries)
      setRepresentatives(
        representatives.map((r) => ({ ...r, summary: undefined }))
      );

      // Start polling for research results
      startPolling(job_id);
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setLoading(false);
    }
  }, [startPolling, stopPolling]);

  return { representatives, loading, error, lookup };
}
```

Key changes:
- No more `ReadableStream`, SSE parsing, `handleSSEEvent`, `receivedDone`, `jobIdRef`
- `lookup()` is now a simple fetch → parse JSON → start polling
- `startPolling` is unchanged from the current implementation (it already works)
- Added `useEffect` cleanup to stop polling and abort fetch on unmount
- `deliveredRef` kept to avoid re-rendering already-delivered research
- Public API `{ representatives, loading, error, lookup }` unchanged — no component changes needed

- [ ] **Step 2: Verify types compile**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useRepresentatives.ts
git commit -m "feat: replace SSE with plain fetch + polling for research results"
```

---

## Chunk 3: Smoke Test

### Task 6: Manual end-to-end verification

- [ ] **Step 1: Start the backend**

```bash
conda activate my-reps && cd backend && uvicorn main:app --reload
```

- [ ] **Step 2: Start the frontend**

```bash
cd frontend && npm run dev
```

- [ ] **Step 3: Test happy path**

1. Enter a valid address in the UI
2. Verify: reps appear immediately after a few seconds of loading
3. Verify: research results trickle in over the next ~30-60s
4. Verify: loading indicator clears when all research is done

- [ ] **Step 4: Test the POST endpoint directly**

```bash
curl -s -X POST http://localhost:8000/api/representatives \
  -H "Content-Type: application/json" \
  -d '{"address": "1600 Pennsylvania Ave, Washington DC"}' | python -m json.tool
```

Verify response is plain JSON with `job_id` and `representatives` array (no SSE formatting).

- [ ] **Step 5: Test polling endpoint**

Using the `job_id` from Step 4:

```bash
curl -s http://localhost:8000/api/jobs/{job_id} | python -m json.tool
```

Verify: returns job status with research entries.

- [ ] **Step 6: Verify frontend build**

```bash
cd frontend && npm run build
```

Expected: Clean build with no errors.

- [ ] **Step 7: Final commit (if any fixups needed)**

```bash
git add -A && git commit -m "fix: address issues found during smoke test"
```
