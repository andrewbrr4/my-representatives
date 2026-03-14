import asyncio
import json
import logging
import os
import uuid

from fastapi import APIRouter, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sse_starlette.sse import EventSourceResponse

from models import AddressRequest, Representative, RepresentativesResponse
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
        # Check cache first (unless disabled)
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
):
    if not address_request.address.strip():
        raise HTTPException(status_code=400, detail="Address is required.")

    skip_cache = fresh or os.getenv("DISABLE_REP_CACHE", "").lower() in ("true", "1")
    if skip_cache:
        logger.info("Research cache disabled for this request")

    logger.info(f"Looking up representatives for: {address_request.address}")

    async def event_stream():
        job_store = get_job_store()

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
            yield {
                "event": "error",
                "data": json.dumps({"detail": "Could not look up representatives for that address. Please check the address and try again."}),
            }
            return

        if not reps:
            yield {
                "event": "error",
                "data": json.dumps({"detail": "No representatives found for that address."}),
            }
            return

        # Sort by level priority
        level_order = {"federal": 0, "state": 1, "municipal": 2}
        reps.sort(key=lambda r: level_order.get(r.level, 3))

        # Phase 2: Send all reps immediately (without summaries)
        yield {
            "event": "representatives",
            "data": RepresentativesResponse(representatives=reps).model_dump_json(),
        }

        # Phase 3: Create job and send job_id to client
        job_id = uuid.uuid4().hex[:12]
        await job_store.create_job(job_id, reps)
        yield {
            "event": "job",
            "data": json.dumps({"job_id": job_id}),
        }

        # Phase 4: Spawn research as a background task (survives SSE disconnect)
        logger.info(f"Job {job_id}: starting research for {len(reps)} reps")
        research_task = asyncio.create_task(_run_all_research(job_id, reps, skip_cache=skip_cache))

        # Phase 5: Poll job store and stream results as they arrive
        delivered: set[int] = set()
        while True:
            job = await job_store.get_job(job_id)
            if job is None:
                break

            # Yield any newly completed research
            for entry in job["research"]:
                idx = entry["index"]
                if idx not in delivered and entry["status"] in ("complete", "failed"):
                    delivered.add(idx)
                    yield {
                        "event": "research",
                        "data": json.dumps({
                            "index": idx,
                            "summary": entry["summary"],
                        }),
                    }

            if job["status"] in ("done", "error"):
                break

            await asyncio.sleep(0.5)

        yield {"event": "done", "data": "{}"}

        # Ensure research task doesn't leak if we exit early
        if not research_task.done():
            # Don't cancel — let it finish writing to the store
            pass

    return EventSourceResponse(event_stream())
