"""Depth subgraph — focused per-topic ReAct subagent with isolated state.

State (DepthState) is fully isolated from the parent. The subagent's
``messages`` (Tavily search results, agent reasoning) live and die in
this scope. Only the structured ``findings`` list crosses back to the
caller (the ``request_depth_research`` tool).
"""

import logging
import os
from datetime import date
from pathlib import Path
from string import Template

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from research.overview.v4.models import Finding
from research.overview.v4.state import DepthState
from research.overview.v4.tools.tavily_search import depth_web_search

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_DEPTH_RECURSION_LIMIT = int(os.getenv("OVERVIEW_V4_DEPTH_RECURSION_LIMIT", "8"))


class _FindingsList(BaseModel):
    """LLM-facing schema used by the depth subagent's finalize node."""

    findings: list[Finding] = Field(default_factory=list)


def _build_initial_messages(state: DepthState) -> list:
    system_template = Template((_PROMPTS_DIR / "depth_agent_system.txt").read_text())
    user_template = Template((_PROMPTS_DIR / "depth_agent_user.txt").read_text())
    system_prompt = system_template.substitute(current_date=date.today().isoformat())
    user_prompt = user_template.substitute(
        name=state["rep"].name,
        office=state["rep"].office,
        topic=state["topic"],
        reason=state["reason"],
    )
    return [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]


async def _agent_node(state: DepthState) -> dict:
    """LLM node: bound to depth_web_search tool. Adds initial system+user
    messages on the first turn (when ``messages`` is empty) so callers
    don't need to construct them."""
    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    ).bind_tools([depth_web_search])

    messages = state.get("messages") or []
    if not messages:
        messages = _build_initial_messages(state)
    response = await model.ainvoke(messages)
    # If we seeded the initial messages, return them along with the
    # response so add_messages picks them up into state.
    if not state.get("messages"):
        return {"messages": messages + [response]}
    return {"messages": [response]}


def _route_after_agent(state: DepthState) -> str:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return "finalize"


async def _finalize_node(state: DepthState) -> dict:
    """Extract a structured ``list[Finding]`` from the depth conversation.

    Uses a fresh model instance with ``with_structured_output`` — the
    extractor sees the full message history and emits ``Finding`` objects.
    """
    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    ).with_structured_output(_FindingsList)

    extraction_prompt = SystemMessage(
        content=(
            f"You are extracting structured findings from a depth-research "
            f"conversation about an elected official, focused on the topic: "
            f"{state['topic']!r}. Read the conversation that follows and emit "
            "a list of Finding objects (claim, source_urls, topic). The "
            "``topic`` field on every Finding should be set to "
            f"{state['topic']!r}. Cite only URLs that appeared in the "
            "search results. If the conversation surfaced no usable claims, "
            "return an empty findings list."
        )
    )
    result = await model.ainvoke([extraction_prompt, *state["messages"]])
    findings = [
        Finding(claim=f.claim, source_urls=f.source_urls, topic=state["topic"])
        for f in result.findings
    ]
    logger.info(
        f"[v4] Depth subagent finalize for topic={state['topic']!r}: "
        f"{len(findings)} findings"
    )
    return {"findings": findings}


def build_depth_graph():
    g = StateGraph(DepthState)
    g.add_node("agent", _agent_node)
    g.add_node("tools", ToolNode([depth_web_search]))
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


# Module-level compiled subgraph. Reused across all depth tool calls
# in a pipeline run; LangGraph compiled graphs are stateless.
depth_graph = build_depth_graph()

# Re-export for callers/tests.
DEPTH_RECURSION_LIMIT = _DEPTH_RECURSION_LIMIT


__all__ = ["DEPTH_RECURSION_LIMIT", "build_depth_graph", "depth_graph"]
