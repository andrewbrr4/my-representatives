"""Depth subagent's Tavily tool — returns ``Command(update=...)`` so raw
search results accumulate in ``DepthState.search_results`` while a
formatted snippet block goes back to the LLM as a ``ToolMessage``.

The structured ``SearchResult`` list is what crosses out of the depth
scope (the research_agent node merges it into V4State).
The full ``ToolMessage`` history stays inside ``DepthState``.
"""

import logging
import os
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.types import Command

from research.overview.models import SearchResult
from research.search import tavily_search_raw

logger = logging.getLogger(__name__)

_DEPTH_RESULTS_PER_QUERY = int(os.getenv("OVERVIEW_V4_DEPTH_RESULTS_PER_QUERY", "5"))
_SNIPPET_CHAR_CAP = int(os.getenv("OVERVIEW_V4_SNIPPET_CHAR_CAP", "800"))


def _format_for_llm(results: list[SearchResult]) -> str:
    if not results:
        return "(no results)"
    parts = []
    for r in results:
        header = f"**{r.title}**\n{r.url}"
        if r.published_date:
            header += f"\nPublished: {r.published_date}"
        parts.append(f"{header}\n{r.snippet}")
    return "\n\n".join(parts)


@tool
async def depth_tavily_search(
    query: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Search the web for current information. Returns relevant search
    results with snippets. Use focused queries for the topic you're
    investigating."""
    raw = await tavily_search_raw(query, max_results=_DEPTH_RESULTS_PER_QUERY)
    results = [
        SearchResult(
            url=r.get("url", ""),
            title=r.get("title", ""),
            snippet=(r.get("snippet", "") or "")[:_SNIPPET_CHAR_CAP],
            published_date=r.get("published_date", "") or "",
        )
        for r in raw
    ]
    formatted = _format_for_llm(results)
    logger.info(f"[v4] depth_tavily_search query={query!r} → {len(results)} results")
    return Command(
        update={
            "search_results": results,
            "messages": [ToolMessage(content=formatted, tool_call_id=tool_call_id)],
        }
    )


__all__ = ["depth_tavily_search"]
