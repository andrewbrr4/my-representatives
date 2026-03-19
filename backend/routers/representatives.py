import asyncio
import logging
import os

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from models import AddressRequest, RepresentativesResponse
from services.cicero import get_state_local_representatives
from services.congress import get_federal_representatives

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.post("/api/representatives")
@limiter.limit("10/minute")
async def lookup_representatives(
    request: Request,
    address_request: AddressRequest,
) -> RepresentativesResponse:
    if not address_request.address.strip():
        raise HTTPException(status_code=400, detail="Address is required.")

    logger.info(f"Looking up representatives for: {address_request.address}")

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

    return RepresentativesResponse(representatives=reps)
