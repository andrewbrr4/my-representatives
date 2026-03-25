import asyncio
import logging
import os
import uuid
from decimal import Decimal

from fastapi import APIRouter, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from db import save_research_task, save_transactions
from models import (
    AddressRequest,
    ElectionResearchRequest,
    ElectionResearchResponse,
    ElectionResearchSummary,
    ElectionsResponse,
)
from research.election_pipeline import ELECTION_TOTAL_SECTIONS, research_election
from services.elections import address_hash, fetch_elections
from store.dependencies import get_election_cache, get_research_store

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

MAX_AUTO_RESEARCH = 3


def _cost_config() -> dict:
    input_cost_env = os.environ.get("ANTHROPIC_INPUT_COST_PER_M")
    output_cost_env = os.environ.get("ANTHROPIC_OUTPUT_COST_PER_M")
    search_cost_env = os.environ.get("COST_PER_SEARCH")
    return {
        "model": os.environ.get("CLAUDE_MODEL"),
        "input_cost_per_m": Decimal(input_cost_env) if input_cost_env else None,
        "output_cost_per_m": Decimal(output_cost_env) if output_cost_env else None,
        "search_tool": os.environ.get("SEARCH_TOOL", "tavily"),
        "cost_per_search": Decimal(search_cost_env) if search_cost_env else None,
        "environment": os.environ.get("ENVIRONMENT", "dev"),
    }


async def _run_election_research(
    research_id: str, req: ElectionResearchRequest
) -> None:
    """Background task: research one election, write to store + cache + DB."""
    store = get_research_store()
    election_cache = get_election_cache()
    addr_hash = address_hash(req.address)

    try:
        summary, usage = await research_election(
            election_name=req.election_name,
            election_date=req.election_date,
            election_type=req.election_type,
            state=req.state,
            address=req.address,
            store=store,
            research_id=research_id,
        )
        if summary is not None:
            await election_cache.put(req.election_name, req.election_date, addr_hash, summary)
        else:
            await store.fail(research_id)
    except Exception as e:
        logger.error(f"Election research {research_id} failed: {e}", exc_info=True)
        await store.fail(research_id)
        return

    cfg = _cost_config()
    try:
        await save_research_task(
            research_id=research_id,
            target=f"{req.election_name}|{req.election_date}",
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            tool_calls=usage.tool_calls,
            status="done" if summary else "failed",
            task_type="election",
            **cfg,
        )
        await save_transactions(
            research_task_id=research_id,
            model=cfg["model"],
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            input_cost_per_m=cfg["input_cost_per_m"],
            output_cost_per_m=cfg["output_cost_per_m"],
            search_tool=cfg["search_tool"],
            tool_calls=usage.tool_calls,
            cost_per_search=cfg["cost_per_search"],
        )
    except Exception as e:
        logger.error(f"Election research {research_id}: DB save failed: {e}", exc_info=True)


@router.post("/api/elections")
@limiter.limit("10/minute")
async def get_elections(request: Request, body: AddressRequest) -> ElectionsResponse:
    """Fetch upcoming elections for an address and auto-trigger research."""
    elections_resp = await fetch_elections(body.address)

    # Auto-trigger election research for up to MAX_AUTO_RESEARCH elections
    store = get_research_store()
    election_cache = get_election_cache()
    addr_hash = address_hash(body.address)
    research_ids: dict[str, str] = {}

    # Extract state from address (simple heuristic: second-to-last comma-separated part)
    parts = [p.strip() for p in body.address.split(",")]
    state = parts[-2] if len(parts) >= 3 else parts[-1] if parts else ""
    # Strip zip code if state part contains it (e.g., "TX 78701")
    state = state.split()[0] if state else ""

    for election in elections_resp.elections[:MAX_AUTO_RESEARCH]:
        ekey = f"{election.name}|{election.date}"

        # Skip if already cached
        cached = await election_cache.get(election.name, election.date, addr_hash)
        if cached is not None:
            research_ids[ekey] = "cached"
            continue

        research_id = uuid.uuid4().hex[:12]
        research_ids[ekey] = research_id
        await store.create(
            research_id,
            total_sections=ELECTION_TOTAL_SECTIONS,
            summary=ElectionResearchSummary(),
        )
        req = ElectionResearchRequest(
            election_name=election.name,
            election_date=election.date,
            election_type=election.election_type,
            state=state,
            address=body.address,
        )
        asyncio.create_task(_run_election_research(research_id, req))

    elections_resp.research_ids = research_ids
    return elections_resp


@router.post("/api/election-research")
@limiter.limit("10/minute")
async def start_election_research(
    request: Request, body: ElectionResearchRequest
) -> ElectionResearchResponse:
    """Manually trigger election research (for elections beyond auto-research cap)."""
    election_cache = get_election_cache()
    addr_hash = address_hash(body.address)

    # Check cache
    skip_cache = os.getenv("DISABLE_REP_CACHE", "").lower() in ("true", "1")
    if not skip_cache:
        cached = await election_cache.get(body.election_name, body.election_date, addr_hash)
        if cached is not None:
            return ElectionResearchResponse(
                research_id="cached",
                status="complete",
                summary=cached,
            )

    research_id = uuid.uuid4().hex[:12]
    store = get_research_store()
    await store.create(
        research_id,
        total_sections=ELECTION_TOTAL_SECTIONS,
        summary=ElectionResearchSummary(),
    )
    asyncio.create_task(_run_election_research(research_id, body))

    return ElectionResearchResponse(research_id=research_id, status="pending")


@router.get("/api/election-research/{research_id}")
async def get_election_research(research_id: str) -> ElectionResearchResponse:
    from fastapi import HTTPException
    task = await get_research_store().get(research_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Election research task not found or expired.")
    return ElectionResearchResponse(
        research_id=task.research_id,
        status=task.status,
        summary=task.summary,
    )
