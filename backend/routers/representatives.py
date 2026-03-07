import asyncio
import logging

from fastapi import APIRouter, HTTPException

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


@router.post("/api/representatives", response_model=RepresentativesResponse)
async def lookup_representatives(request: AddressRequest):
    if not request.address.strip():
        raise HTTPException(status_code=400, detail="Address is required.")

    logger.info(f"Looking up representatives for: {request.address}")

    try:
        federal_reps, state_local_reps = await asyncio.gather(
            get_federal_representatives(request.address),
            get_state_local_representatives(request.address),
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

    logger.info(f"Found {len(reps)} representatives, starting research")

    # Research all reps concurrently
    researched = await asyncio.gather(
        *[_research_with_fallback(rep) for rep in reps]
    )
    logger.info("Research complete for all representatives")

    # Sort by level priority
    level_order = {"federal": 0, "state": 1, "municipal": 2}
    researched.sort(key=lambda r: level_order.get(r.level, 3))

    return RepresentativesResponse(representatives=researched)
