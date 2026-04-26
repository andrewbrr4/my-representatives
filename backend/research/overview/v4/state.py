"""LangGraph state schemas for v4.

Three TypedDicts, one per scope. State isolation across subgraph
boundaries is the architectural argument for v4: a depth subagent's
``messages`` history (potentially N tool results) lives and dies in
``DepthState`` and never propagates to ``V4State`` — only structured
``findings`` cross the boundary.

Reducers (``Annotated[..., operator.add]`` and ``add_messages``) are
required only on fields that receive concurrent writes from parallel
branches.
"""

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from models import Representative
from research.overview.v4.models import Finding, ResearchSummary, SearchResult


class V4State(TypedDict, total=False):
    """Top-level pipeline state."""

    rep: Representative
    queries: list[str]
    raw_results: Annotated[list[SearchResult], operator.add]   # parallel-merge
    filtered_results: list[SearchResult]
    findings: list[Finding]
    summary: ResearchSummary | None


class ResearchAgentState(TypedDict, total=False):
    """Inner state for the research_agent subgraph.

    ``filtered_results`` and ``rep`` are passed in by the wrapper.
    ``messages`` is the agent's ReAct conversation; it is NOT lifted to
    ``V4State``. ``depth_findings`` accumulates structured findings from
    each ``request_depth_research`` tool call (via ``Command(update=...)``).
    ``findings`` is the final structured output emitted by the
    ``finalize`` node — this is what crosses back to ``V4State``.
    """

    rep: Representative
    filtered_results: list[SearchResult]
    messages: Annotated[list[BaseMessage], add_messages]
    depth_findings: Annotated[list[Finding], operator.add]
    findings: list[Finding]


class DepthState(TypedDict, total=False):
    """Inner state for one depth subagent run.

    Receives only ``rep``, ``topic``, ``reason``. Returns only
    ``findings``. Its ``messages`` history (Tavily search results, agent
    reasoning) never leaves this scope.
    """

    rep: Representative
    topic: str
    reason: str
    messages: Annotated[list[BaseMessage], add_messages]
    findings: list[Finding]


__all__ = ["DepthState", "ResearchAgentState", "V4State"]
