"""``request_depth_research`` tool factory — the bridge between
research_agent and depth_subgraph.

Returns a ``Command(update=...)`` so depth findings are written
directly into the parent research_agent's state via LangGraph's
state-from-tool pattern. The tool ALSO returns a ``ToolMessage``
(carried inside the Command) so the agent sees a conversational
acknowledgement of its tool call.
"""

import logging
from typing import Annotated, Callable

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.types import Command

from models import Representative
from research.overview.v4.nodes.depth_subgraph import (
    DEPTH_RECURSION_LIMIT,
    depth_graph,
)

logger = logging.getLogger(__name__)


def _format_findings_for_agent(findings: list, topic: str) -> str:
    if not findings:
        return f"Depth research on '{topic}' returned no usable findings."
    lines = [f"Depth research on '{topic}' — {len(findings)} finding(s):"]
    for i, f in enumerate(findings, start=1):
        urls = ", ".join(f.source_urls[:3])
        lines.append(f"  {i}. {f.claim} (sources: {urls})")
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
        try:
            result = await depth_graph.ainvoke(
                {
                    "rep": rep,
                    "topic": topic,
                    "reason": reason,
                    "messages": [],
                    "findings": [],
                },
                config={"recursion_limit": DEPTH_RECURSION_LIMIT},
            )
        except Exception as e:
            logger.error(f"[v4] Depth subgraph failed for topic={topic!r}: {e}", exc_info=True)
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

        findings = result.get("findings", [])
        summary = _format_findings_for_agent(findings, topic)
        return Command(
            update={
                "depth_findings": findings,
                "messages": [
                    ToolMessage(content=summary, tool_call_id=tool_call_id)
                ],
            }
        )

    return request_depth_research


__all__ = ["make_request_depth_tool"]
