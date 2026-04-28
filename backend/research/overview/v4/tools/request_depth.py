"""``request_depth_research`` tool factory — the bridge between
research_agent and the depth subagent.

Returns a ``Command(update=...)`` so depth-derived ``SearchResult``
objects are written directly into the parent research_agent's state via
LangGraph's state-from-tool pattern. The tool ALSO returns a
``ToolMessage`` (carried inside the Command) so the agent sees a
conversational acknowledgement of its tool call.
"""

import logging
from typing import Annotated, Callable

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.types import Command

from models import Representative
from research.overview.v4.models import SearchResult
from research.overview.v4.nodes.depth_subgraph import (
    DEPTH_RECURSION_LIMIT,
    build_depth_agent,
    build_depth_initial_user_message,
)

logger = logging.getLogger(__name__)


def _format_results_for_agent(results: list[SearchResult], topic: str) -> str:
    if not results:
        return f"Depth research on '{topic}' returned no usable results."
    lines = [f"Depth research on '{topic}' — {len(results)} result(s):"]
    for i, r in enumerate(results, start=1):
        date_suffix = f" (Published: {r.published_date})" if r.published_date else ""
        lines.append(f"  {i}. {r.title}{date_suffix} — {r.url}")
    return "\n".join(lines)


def make_request_depth_tool(rep: Representative) -> Callable:
    """Build the depth-research tool bound to this pipeline run's rep.

    The tool is constructed per-pipeline-run so ``rep`` is captured via
    closure and never exposed to the LLM.
    """

    @tool
    async def request_depth_research(
        topic: str,
        reason: str,
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        """Run a focused depth investigation on a specific subtopic. Use only
        for volatile/time-sensitive claims (ongoing controversies, pending
        litigation, candidacy status, breaking news). Argument ``topic`` is
        the subject to investigate; ``reason`` briefly explains why depth
        is needed."""
        logger.info(f"[v4] Depth research requested for topic={topic!r} reason={reason!r}")
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
                config={"recursion_limit": DEPTH_RECURSION_LIMIT},
            )
        except Exception as e:
            logger.error(f"[v4] Depth subagent failed for topic={topic!r}: {e}", exc_info=True)
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=f"Depth research on '{topic}' failed: {e}",
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

        depth_results = result.get("search_results") or []
        # Tag depth-derived results with the topic at the boundary, so
        # downstream nodes (formatter) can label them in their prompt.
        tagged = [
            SearchResult(
                url=r.url,
                title=r.title,
                snippet=r.snippet,
                published_date=r.published_date,
                topic=topic,
            )
            for r in depth_results
        ]
        ack = _format_results_for_agent(tagged, topic)
        return Command(
            update={
                "depth_search_results": tagged,
                "messages": [ToolMessage(content=ack, tool_call_id=tool_call_id)],
            }
        )

    return request_depth_research


__all__ = ["make_request_depth_tool"]
