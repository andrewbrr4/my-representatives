import asyncio
import logging
import os
import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from models import AddressRequest, LookupResponse, Representative
from services.cicero import get_state_local_representatives
from services.congress import get_federal_representatives
from db import save_job, save_transactions
from research.pipeline import research_representative
from research.usage import UsageStats
from store.dependencies import get_job_store, get_rep_cache

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


async def _research_rep_to_store(
    job_id: str, index: int, rep: Representative
) -> UsageStats:
    """Research a single rep, writing results to job store and rep cache."""
    job_store = get_job_store()
    rep_cache = get_rep_cache()
    try:
        summary, usage = await research_representative(rep)
        await job_store.update_rep_research(job_id, index, summary, failed=summary is None)
        if summary is not None:
            await rep_cache.put(rep.name, rep.office, summary)
        return usage
    except Exception as e:
        logger.warning(f"Research failed for {rep.name}: {e}")
        await job_store.update_rep_research(job_id, index, None, failed=True)
        return UsageStats()


async def _run_all_research(job_id: str, address: str, reps: list[Representative], skip_cache: bool = False) -> None:
    """Fire-and-forget: research all reps and mark job done when finished."""
    job_store = get_job_store()
    rep_cache = get_rep_cache()

    tasks = []
    cached_count = 0
    for i, rep in enumerate(reps):
        # Check cache first (unless disabled)
        if not skip_cache:
            cached = await rep_cache.get(rep.name, rep.office)
            if cached is not None:
                await job_store.update_rep_research(job_id, i, cached)
                cached_count += 1
                continue
        tasks.append(asyncio.create_task(_research_rep_to_store(job_id, i, rep)))

    total_usage = UsageStats()
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, UsageStats):
                total_usage += result

    await job_store.mark_done(job_id)
    logger.info(
        f"Job {job_id}: research complete — "
        f"{len(reps)} reps ({cached_count} cached, {len(tasks)} researched) — "
        f"{total_usage.input_tokens:,} input tokens, "
        f"{total_usage.output_tokens:,} output tokens, "
        f"{total_usage.total_tokens:,} total tokens, "
        f"{total_usage.tool_calls} tool calls"
    )

    # Snapshot pricing at request time so historical data survives rate changes
    model = os.environ.get("CLAUDE_MODEL")
    input_cost_env = os.environ.get("ANTHROPIC_INPUT_COST_PER_M")
    output_cost_env = os.environ.get("ANTHROPIC_OUTPUT_COST_PER_M")
    search_cost_env = os.environ.get("COST_PER_SEARCH")
    input_cost_per_m = Decimal(input_cost_env) if input_cost_env else None
    output_cost_per_m = Decimal(output_cost_env) if output_cost_env else None
    search_tool = "tavily"
    cost_per_search = Decimal(search_cost_env) if search_cost_env else None
    environment = os.environ.get("ENVIRONMENT", "dev")

    try:
        await save_job(
            job_id=job_id,
            address=address,
            reps_found=len(reps),
            reps_researched=len(tasks),
            reps_cached=cached_count,
            input_tokens=total_usage.input_tokens,
            output_tokens=total_usage.output_tokens,
            tool_calls=total_usage.tool_calls,
            status="done",
            model=model,
            input_cost_per_m=input_cost_per_m,
            output_cost_per_m=output_cost_per_m,
            search_tool=search_tool,
            cost_per_search=cost_per_search,
            environment=environment,
        )
        await save_transactions(
            job_id=job_id,
            model=model,
            input_tokens=total_usage.input_tokens,
            output_tokens=total_usage.output_tokens,
            input_cost_per_m=input_cost_per_m,
            output_cost_per_m=output_cost_per_m,
            search_tool=search_tool,
            tool_calls=total_usage.tool_calls,
            cost_per_search=cost_per_search,
        )
        logger.info(f"Job {job_id}: saved to database")
    except Exception as e:
        logger.error(f"Job {job_id}: failed to save to database: {e}", exc_info=True)


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
    asyncio.create_task(_run_all_research(job_id, address_request.address, reps, skip_cache=skip_cache))

    # Phase 3: Return reps + job_id as plain JSON
    return LookupResponse(job_id=job_id, representatives=reps)
