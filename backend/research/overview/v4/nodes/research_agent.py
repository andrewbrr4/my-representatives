"""Research-agent subgraph + V4State wrapper node.

Subgraph topology:
  agent ──tool_calls──▶ tools ──▶ agent
  agent ──no calls──▶ finalize ──▶ END

State boundary: only ``findings`` (the structured output of finalize)
crosses back to V4State. The agent's ``messages`` history and
``depth_findings`` accumulator stay inside ResearchAgentState.
"""

import logging
import os
from datetime import date
from pathlib import Path
from string import Template

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langfuse import observe
from langfuse.langchain import CallbackHandler
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from research.overview.v4.models import Finding, SearchResult
from research.overview.v4.state import ResearchAgentState, V4State
from research.overview.v4.tools.request_depth import make_request_depth_tool
from research.usage import UsageTracker

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_AGENT_RECURSION_LIMIT = 12
_MAX_DEPTH_CALLS = int(os.getenv("OVERVIEW_V4_AGENT_MAX_DEPTH_CALLS", "3"))


class _FindingsList(BaseModel):
    findings: list[Finding] = Field(default_factory=list)


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


def _build_initial_messages(state: ResearchAgentState) -> list:
    system_template = Template((_PROMPTS_DIR / "research_agent_system.txt").read_text())
    user_template = Template((_PROMPTS_DIR / "research_agent_user.txt").read_text())
    system_prompt = system_template.substitute(
        current_date=date.today().isoformat(),
        max_depth_calls=str(_MAX_DEPTH_CALLS),
    )
    user_prompt = user_template.substitute(
        name=state["rep"].name,
        office=state["rep"].office,
        results_block=_format_results_block(state["filtered_results"]),
        max_depth_calls=str(_MAX_DEPTH_CALLS),
    )
    return [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]


def build_research_agent_graph(request_depth_tool):
    """Build (and compile) a research_agent subgraph bound to ``request_depth_tool``.

    The tool is rep-specific (closure-bound), so the graph is built per
    pipeline run.
    """

    async def _agent_node(state: ResearchAgentState) -> dict:
        model = ChatAnthropic(
            model=os.environ["CLAUDE_MODEL"],
            max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
        ).bind_tools([request_depth_tool])

        messages = state.get("messages") or []
        if not messages:
            messages = _build_initial_messages(state)
        response = await model.ainvoke(messages)
        if not state.get("messages"):
            return {"messages": messages + [response]}
        return {"messages": [response]}

    def _route_after_agent(state: ResearchAgentState) -> str:
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        return "finalize"

    async def _finalize_node(state: ResearchAgentState) -> dict:
        """Extract structured findings from filtered_results + depth_findings.

        Depth findings carry authoritative-fresh information for their
        topics; the extractor is told to prefer them on overlap.
        """
        model = ChatAnthropic(
            model=os.environ["CLAUDE_MODEL"],
            max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
        ).with_structured_output(_FindingsList)

        depth = state.get("depth_findings") or []
        depth_block = "(none)"
        if depth:
            lines = []
            for f in depth:
                urls = ", ".join(f.source_urls[:3])
                lines.append(
                    f"- topic={f.topic!r}: {f.claim} (sources: {urls})"
                )
            depth_block = "\n".join(lines)

        extraction_prompt = SystemMessage(
            content=(
                "You are extracting structured Finding objects from research "
                "material about an elected official. For every Finding: "
                "claim is one factual sentence; source_urls lists URLs from "
                "the materials below; topic is a short category like "
                "'policy', 'record', 'controversy', 'donors', 'candidacy'.\n\n"
                "When the breadth results and depth findings overlap on a "
                "topic, the DEPTH FINDINGS are authoritative-fresh — prefer "
                "them and discard stale breadth claims on that topic.\n\n"
                "Cite only URLs that actually appear in the materials. "
                "Aim for 8–14 findings total (fewer is fine if breadth is "
                "thin). Do not invent claims."
            )
        )

        materials = HumanMessage(
            content=(
                f"Official: {state['rep'].name}\n"
                f"Office: {state['rep'].office}\n\n"
                f"Pre-filtered breadth search results:\n\n"
                f"{_format_results_block(state['filtered_results'])}\n\n"
                f"---\n\nDepth-research findings (authoritative-fresh):\n\n"
                f"{depth_block}\n\n"
                f"---\n\nExtract Findings now."
            )
        )

        result = await model.ainvoke([extraction_prompt, materials])
        logger.info(
            f"[v4] research_agent finalize for {state['rep'].name}: "
            f"{len(result.findings)} findings (depth contributed "
            f"{len(depth)})"
        )
        return {"findings": result.findings}

    g = StateGraph(ResearchAgentState)
    g.add_node("agent", _agent_node)
    g.add_node("tools", ToolNode([request_depth_tool]))
    g.add_node("finalize", _finalize_node)
    g.add_edge(START, "agent")
    g.add_conditional_edges(
        "agent",
        _route_after_agent,
        {"tools": "tools", "finalize": "finalize"},
    )
    g.add_edge("tools", "agent")
    g.add_edge("finalize", END)
    return g.compile()


@observe(name="v4-research-agent")
async def research_agent_node(state: V4State) -> dict:
    """V4State wrapper: build the per-run subgraph, invoke it, return only
    ``findings`` to V4State. The agent's messages and depth_findings
    accumulator stay inside ResearchAgentState and are dropped at the
    boundary.
    """
    rep = state["rep"]
    langfuse_handler = CallbackHandler()
    usage_tracker = UsageTracker()

    request_depth_tool = make_request_depth_tool(rep)
    agent_graph = build_research_agent_graph(request_depth_tool)

    inner: ResearchAgentState = {
        "rep": rep,
        "filtered_results": state["filtered_results"],
        "messages": [],
        "depth_findings": [],
        "findings": [],
    }
    result = await agent_graph.ainvoke(
        inner,
        config={
            "callbacks": [langfuse_handler, usage_tracker],
            "recursion_limit": _AGENT_RECURSION_LIMIT,
            "run_name": f"v4:research-agent:{rep.name}",
        },
    )
    findings = result.get("findings") or []
    logger.info(
        f"[v4] research_agent_node for {rep.name}: {len(findings)} findings, "
        f"{usage_tracker.stats.tool_calls} depth calls"
    )
    return {"findings": findings, "usage_log": [usage_tracker.stats]}


__all__ = [
    "build_research_agent_graph",
    "research_agent_node",
]
