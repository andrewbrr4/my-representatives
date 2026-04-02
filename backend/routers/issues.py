import asyncio
import logging
import os
import uuid

from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from config import cost_config
from db import save_research_task, save_transactions
from models import (
    IssueMatchRequest,
    IssueMatchResponse,
    IssueResearchRequest,
    IssueResearchResponse,
    IssueStanceSummary,
)
from research.issue_pipeline import (
    ISSUE_TOTAL_SECTIONS,
    REJECTION_MESSAGE,
    match_issue,
    research_issue_stance,
)
from store.dependencies import get_issue_cache, get_research_store

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


async def _run_issue_research(research_id: str, req: IssueResearchRequest) -> None:
    """Background task: research one rep's stance on one issue."""
    store = get_research_store()
    issue_cache = get_issue_cache()
    rep = req.representative

    try:
        items, citations, usage = await research_issue_stance(
            rep=rep,
            issue_label=req.issue_label,
            store=store,
            research_id=research_id,
        )
        if items is not None:
            summary = IssueStanceSummary(stance_summary=items, citations=citations)
            await issue_cache.put(rep.name, rep.office, req.issue_id, summary)
        else:
            await store.fail(research_id)
    except Exception as e:
        logger.error(f"Issue research {research_id} failed for {rep.name}: {e}", exc_info=True)
        await store.fail(research_id)
        return

    cfg = cost_config()
    try:
        await save_research_task(
            research_id=research_id,
            target=f"{rep.name} ({rep.office}) | {req.issue_label}",
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            tool_calls=usage.tool_calls,
            status="done" if items else "failed",
            task_type="issue",
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
        logger.info(f"Issue research {research_id}: saved to database")
    except Exception as e:
        logger.error(f"Issue research {research_id}: DB save failed: {e}", exc_info=True)


@router.post("/api/issue-match")
@limiter.limit("20/minute")
async def issue_match(request: Request, body: IssueMatchRequest) -> IssueMatchResponse:
    """Classify a user's issue query against the taxonomy."""
    try:
        matched, issue_info, novel = await match_issue(body.query)
    except Exception as e:
        logger.error(f"Issue match failed for '{body.query}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Issue classification failed.")

    if not matched:
        return IssueMatchResponse(matched=False, message=REJECTION_MESSAGE)

    return IssueMatchResponse(matched=True, issue=issue_info, novel=novel)


@router.post("/api/issue-research")
@limiter.limit("10/minute")
async def start_issue_research(
    request: Request, body: IssueResearchRequest
) -> IssueResearchResponse:
    """Start stance research for one rep on one issue."""
    rep = body.representative

    # Check cache
    skip_cache = os.getenv("DISABLE_REP_CACHE", "").lower() in ("true", "1")
    if not skip_cache:
        cached = await get_issue_cache().get(rep.name, rep.office, body.issue_id)
        if cached is not None:
            return IssueResearchResponse(
                research_id="cached",
                status="complete",
                summary=cached,
            )

    research_id = uuid.uuid4().hex[:12]
    store = get_research_store()
    await store.create(
        research_id,
        total_sections=ISSUE_TOTAL_SECTIONS,
        summary=IssueStanceSummary(),
    )
    asyncio.create_task(_run_issue_research(research_id, body))

    return IssueResearchResponse(research_id=research_id, status="pending")


@router.get("/api/issue-research/{research_id}")
async def get_issue_research(research_id: str) -> IssueResearchResponse:
    """Poll issue research progress."""
    task = await get_research_store().get(research_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Issue research task not found or expired.")
    return IssueResearchResponse(
        research_id=task.research_id,
        status=task.status,
        summary=task.summary,
    )
