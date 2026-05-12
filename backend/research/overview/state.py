"""LangGraph state schemas for v4.

Two state schemas, one per scope. State isolation across subagent
boundaries is the architectural argument for v4: a depth subagent's
``messages`` history (potentially N tool results) lives and dies in
``DepthState`` and never propagates to ``V4State`` — only structured
``SearchResult`` lists cross boundaries.

Reducers (``Annotated[..., operator.add]`` and ``add_messages``) are
required only on fields that receive concurrent writes from parallel
branches.
"""

import operator
from typing import Annotated, TypedDict

from langchain.agents import AgentState

from models import Representative
from research.overview.models import ResearchSummary, SearchResult
from research.usage import UsageStats


class V4State(TypedDict, total=False):
    """Top-level pipeline state."""

    rep: Representative
    queries: list[str]
    raw_results: Annotated[list[SearchResult], operator.add]   # parallel-merge
    filtered_results: list[SearchResult]
    depth_search_results: list[SearchResult]
    summary: ResearchSummary | None
    # Aggregated LLM/tool usage. Each node that does LLM work appends a
    # ``UsageStats`` to this list; the pipeline entrypoint sums them.
    usage_log: Annotated[list[UsageStats], operator.add]


class DepthState(AgentState):
    """Inner state for one depth subagent (also a ``create_agent``).

    Receives ``rep``, ``topic``, ``reason``. The depth Tavily tool writes
    ``SearchResult`` objects into ``search_results`` via ``Command(update=...)``;
    only that list crosses back out. The full ``messages`` history
    (Tavily snippet ToolMessages, agent reasoning) never leaves this scope.
    """

    rep: Representative
    topic: str
    reason: str
    search_results: Annotated[list[SearchResult], operator.add]


__all__ = ["DepthState", "V4State"]
