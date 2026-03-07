import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from models import AddressRequest, Representative, RepresentativesResponse
from services.cicero import get_state_local_representatives
from services.congress import get_federal_representatives
from services.research import research_representative

logger = logging.getLogger(__name__)
router = APIRouter()


async def _research_with_fallback(rep: Representative) -> Representative:
    """Research a rep, falling back to no summary on error."""
    try:
        summary = await research_representative(rep)
        rep.summary = summary
    except Exception as e:
        logger.warning(f"Research failed for {rep.name}: {e}")
        rep.summary = None
    return rep


@router.post("/api/representatives")
async def lookup_representatives(request: AddressRequest):
    if not request.address.strip():
        raise HTTPException(status_code=400, detail="Address is required.")

    logger.info(f"Looking up representatives for: {request.address}")

    async def event_stream():
        # Phase 1: Look up all reps
        try:
            federal_reps, state_local_reps = await asyncio.gather(
                get_federal_representatives(request.address),
                get_state_local_representatives(request.address),
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

        # Phase 3: Research all reps concurrently, stream each as it completes
        logger.info(f"Found {len(reps)} representatives, starting research")

        async def research_and_signal(index: int, rep: Representative, done_queue: asyncio.Queue):
            researched = await _research_with_fallback(rep)
            await done_queue.put((index, researched))

        queue: asyncio.Queue = asyncio.Queue()
        tasks = [
            asyncio.create_task(research_and_signal(i, rep, queue))
            for i, rep in enumerate(reps)
        ]

        for _ in range(len(tasks)):
            index, researched_rep = await queue.get()
            yield {
                "event": "research",
                "data": json.dumps({
                    "index": index,
                    "summary": researched_rep.summary.model_dump() if researched_rep.summary else None,
                }),
            }

        # Make sure all tasks are done
        await asyncio.gather(*tasks)
        logger.info("Research complete for all representatives")

        yield {"event": "done", "data": "{}"}

    return EventSourceResponse(event_stream())
