import asyncio
import logging
import os
import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from db import save_research_task, save_transactions
from models import ResearchRequest, ResearchResponse
from research.pipeline import research_representative
from store.dependencies import get_rep_cache, get_research_store

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


async def _run_research(research_id: str, req: ResearchRequest) -> None:
    """Background task: research one rep, write to store + cache + DB."""
    store = get_research_store()
    rep_cache = get_rep_cache()
    rep = req.representative

    try:
        summary, usage = await research_representative(rep)
        if summary is not None:
            await store.complete(research_id, summary)
            await rep_cache.put(rep.name, rep.office, summary)
        else:
            await store.fail(research_id)
    except Exception as e:
        logger.error(f"Research {research_id} failed for {rep.name}: {e}", exc_info=True)
        await store.fail(research_id)
        return

    # Persist costs
    model = os.environ.get("CLAUDE_MODEL")
    input_cost_env = os.environ.get("ANTHROPIC_INPUT_COST_PER_M")
    output_cost_env = os.environ.get("ANTHROPIC_OUTPUT_COST_PER_M")
    search_cost_env = os.environ.get("COST_PER_SEARCH")
    input_cost_per_m = Decimal(input_cost_env) if input_cost_env else None
    output_cost_per_m = Decimal(output_cost_env) if output_cost_env else None
    search_tool = os.environ.get("SEARCH_TOOL", "tavily")
    cost_per_search = Decimal(search_cost_env) if search_cost_env else None
    environment = os.environ.get("ENVIRONMENT", "dev")

    try:
        await save_research_task(
            research_id=research_id,
            representative=f"{rep.name} ({rep.office})",
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            tool_calls=usage.tool_calls,
            status="done" if summary else "failed",
            model=model,
            input_cost_per_m=input_cost_per_m,
            output_cost_per_m=output_cost_per_m,
            search_tool=search_tool,
            cost_per_search=cost_per_search,
            environment=environment,
        )
        await save_transactions(
            research_task_id=research_id,
            model=model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            input_cost_per_m=input_cost_per_m,
            output_cost_per_m=output_cost_per_m,
            search_tool=search_tool,
            tool_calls=usage.tool_calls,
            cost_per_search=cost_per_search,
        )
        logger.info(f"Research {research_id}: saved to database")
    except Exception as e:
        logger.error(f"Research {research_id}: failed to save to database: {e}", exc_info=True)


@router.post("/api/research")
@limiter.limit("10/minute")
async def start_research(request: Request, body: ResearchRequest) -> ResearchResponse:
    rep = body.representative

    # Check cache first
    skip_cache = os.getenv("DISABLE_REP_CACHE", "").lower() in ("true", "1")
    if not skip_cache:
        cached = await get_rep_cache().get(rep.name, rep.office)
        if cached is not None:
            return ResearchResponse(
                research_id="cached",
                status="complete",
                summary=cached,
            )

    # Create task and spawn background research
    research_id = uuid.uuid4().hex[:12]
    store = get_research_store()
    await store.create(research_id)

    asyncio.create_task(_run_research(research_id, body))

    return ResearchResponse(research_id=research_id, status="pending")


@router.get("/api/research/{research_id}")
async def get_research(research_id: str) -> ResearchResponse:
    task = await get_research_store().get(research_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Research task not found or expired.")
    return ResearchResponse(
        research_id=task.research_id,
        status=task.status,
        summary=task.summary,
    )
