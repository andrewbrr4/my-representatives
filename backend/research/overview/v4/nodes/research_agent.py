"""Research-agent node — structured-output triage + parallel depth fanout.

One LLM call decides which (if any) depth topics to investigate, returning
a ``list[_DepthRequest]``. Selected topics are dispatched concurrently via
``asyncio.gather``; each spawns an isolated depth subagent (``DepthState``).
Depth ``SearchResult`` lists are tagged with their topic and merged into
``depth_search_results`` on V4State.

Replaces the previous ``create_react_agent`` design, where the model emitted
``request_depth_research`` tool calls one at a time across react steps —
serial latency, plus a "think between tools" loop that wasn't buying us
better triage decisions for this use case.
"""

import asyncio
import logging
import os
from datetime import date
from pathlib import Path
from string import Template

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langfuse import observe
from langfuse.langchain import CallbackHandler
from pydantic import BaseModel, Field

from models import Representative
from research.overview.v4.models import SearchResult
from research.overview.v4.nodes.depth_subgraph import (
    DEPTH_RECURSION_LIMIT,
    build_depth_agent,
    build_depth_initial_user_message,
)
from research.overview.v4.state import V4State
from research.usage import UsageStats, UsageTracker

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_MAX_DEPTH_CALLS = int(os.getenv("OVERVIEW_V4_AGENT_MAX_DEPTH_CALLS", "3"))
_DEPTH_ENABLED = os.getenv("OVERVIEW_V4_DEPTH_ENABLED", "true").strip().lower() in (
    "1", "true", "yes", "on"
)


def _model_id() -> str:
    """Per-node model override for the triage call."""
    return os.getenv("OVERVIEW_V4_TRIAGE_MODEL", os.environ["CLAUDE_MODEL"])


class _DepthRequest(BaseModel):
    topic: str = Field(description="Specific subtopic to investigate.")
    reason: str = Field(description="Why depth is needed (Condition 1 or 2).")


class _TriageOutput(BaseModel):
    depth_requests: list[_DepthRequest] = Field(
        default_factory=list,
        description="Topics that warrant a depth call. Empty list = no depth needed.",
    )


def _format_results_block(results: list[SearchResult]) -> str:
    if not results:
        return "(no results)"
    lines = []
    for i, r in enumerate(results, start=1):
        date_suffix = f"  Published: {r.published_date}\n" if r.published_date else ""
        lines.append(
            f"[{i}] {r.title}\n  URL: {r.url}\n{date_suffix}  {r.snippet}"
        )
    return "\n\n".join(lines)


async def _invoke_depth_for_topic(
    rep: Representative, topic: str, reason: str
) -> tuple[list[SearchResult], UsageStats]:
    """Invoke one depth subagent for a single topic; tag its results.

    Errors are caught and logged so a single failed depth call cannot
    abort the parent gather.
    """
    usage_tracker = UsageTracker()
    langfuse_handler = CallbackHandler()
    depth_agent = build_depth_agent()
    initial_state = {
        "rep": rep,
        "topic": topic,
        "reason": reason,
        "search_results": [],
        "messages": [build_depth_initial_user_message({
            "rep": rep,
            "topic": topic,
            "reason": reason,
        })],
    }
    try:
        result = await depth_agent.ainvoke(
            initial_state,
            config={
                "callbacks": [langfuse_handler, usage_tracker],
                "recursion_limit": DEPTH_RECURSION_LIMIT,
                "run_name": f"v4:depth:{topic[:50]}",
            },
        )
    except Exception as e:
        logger.error(f"[v4] Depth subagent failed for topic={topic!r}: {e}", exc_info=True)
        return [], usage_tracker.stats

    raw = result.get("search_results") or []
    tagged = [
        SearchResult(
            url=r.url,
            title=r.title,
            snippet=r.snippet,
            published_date=r.published_date,
            topic=topic,
        )
        for r in raw
    ]
    return tagged, usage_tracker.stats


@observe(name="v4-research-agent")
async def research_agent_node(state: V4State) -> dict:
    """Structured-output triage + parallel depth fanout.

    1. One LLM call (structured output) reviews breadth results and
       returns ``list[_DepthRequest]`` — possibly empty.
    2. Selected requests fan out concurrently via ``asyncio.gather``,
       each invoking an isolated depth subagent.
    3. Tagged depth results merge into ``depth_search_results``.
    """
    rep = state["rep"]
    filtered_results = state.get("filtered_results") or []

    if not _DEPTH_ENABLED:
        logger.info(
            f"[v4] research_agent for {rep.name}: depth disabled "
            f"(OVERVIEW_V4_DEPTH_ENABLED=false); skipping triage + depth subagents"
        )
        return {"depth_search_results": [], "usage_log": []}

    system_template = Template((_PROMPTS_DIR / "research_agent_system.txt").read_text())
    user_template = Template((_PROMPTS_DIR / "research_agent_user.txt").read_text())
    system_prompt = system_template.substitute(
        current_date=date.today().isoformat(),
        max_depth_calls=str(_MAX_DEPTH_CALLS),
    )
    user_prompt = user_template.substitute(
        name=rep.name,
        office=rep.office,
        results_block=_format_results_block(filtered_results),
        max_depth_calls=str(_MAX_DEPTH_CALLS),
    )

    triage_tracker = UsageTracker()
    triage_handler = CallbackHandler()
    model = ChatAnthropic(
        model=_model_id(),
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    )
    structured = model.with_structured_output(_TriageOutput)
    triage = await structured.ainvoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
        config={
            "callbacks": [triage_handler, triage_tracker],
            "run_name": f"v4:triage:{rep.name}",
        },
    )

    requests = (triage.depth_requests or [])[:_MAX_DEPTH_CALLS]
    logger.info(
        f"[v4] research_agent for {rep.name}: triage selected "
        f"{len(requests)} depth topic(s) {[r.topic for r in requests]}"
    )

    if not requests:
        return {
            "depth_search_results": [],
            "usage_log": [triage_tracker.stats],
        }

    fanout = await asyncio.gather(
        *(
            _invoke_depth_for_topic(rep, req.topic, req.reason)
            for req in requests
        )
    )
    depth_search_results: list[SearchResult] = []
    aggregated_depth_stats = UsageStats()
    for results, stats in fanout:
        depth_search_results.extend(results)
        aggregated_depth_stats += stats
    # Each depth request that ran counts as a tool call for accounting
    # parity with the prior react-loop design.
    aggregated_depth_stats.tool_calls += len(requests)

    logger.info(
        f"[v4] research_agent for {rep.name}: {len(depth_search_results)} depth results, "
        f"{len(requests)} depth call(s)"
    )
    return {
        "depth_search_results": depth_search_results,
        "usage_log": [triage_tracker.stats, aggregated_depth_stats],
    }


__all__ = ["research_agent_node"]
