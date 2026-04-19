"""Shared web search tool used by all research pipelines."""

import asyncio
import logging
import os

from langchain_core.tools import tool
from tavily import AsyncTavilyClient

logger = logging.getLogger(__name__)

# Limit concurrent Tavily searches to avoid rate limits
_search_semaphore = asyncio.Semaphore(3)

_MAX_SEARCH_RETRIES = 5
_RETRY_BASE_DELAY = 5.0  # seconds, doubles each retry

_tavily_client: AsyncTavilyClient | None = None


def _get_tavily_client() -> AsyncTavilyClient:
    global _tavily_client
    if _tavily_client is None:
        _tavily_client = AsyncTavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    return _tavily_client


@tool
async def web_search(query: str) -> str:
    """Search the web for current information about a topic. Returns relevant search results with snippets."""
    async with _search_semaphore:
        tavily = _get_tavily_client()
        for attempt in range(_MAX_SEARCH_RETRIES):
            try:
                search_results = await tavily.search(query=query, max_results=5)
                return "\n\n".join(
                    f"**{r['title']}**\n{r['url']}\n{r['content']}"
                    for r in search_results.get("results", [])
                )
            except Exception as e:
                error_detail = str(e)
                if hasattr(e, "response"):
                    try:
                        error_detail = e.response.text
                    except Exception:
                        pass
                is_rate_limit = "429" in error_detail or "rate" in error_detail.lower()
                if is_rate_limit and attempt < _MAX_SEARCH_RETRIES - 1:
                    delay = _RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(f"Search rate-limited, retrying in {delay}s (attempt {attempt + 1})")
                    await asyncio.sleep(delay)
                    continue
                logger.warning(f"Search failed: {error_detail}")
                return "Search failed. Try a different query."
    return "Search failed. Try a different query."
