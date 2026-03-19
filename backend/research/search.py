"""Pluggable web search providers for research agents.

Set SEARCH_TOOL env var to select provider: "tavily" (default) or "serper".
"""

import asyncio
import logging
import os
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

_MAX_RETRIES = 5
_RETRY_BASE_DELAY = 5.0  # seconds, doubles each retry

# Limit concurrent searches to avoid rate limits
semaphore = asyncio.Semaphore(3)


class SearchProvider(ABC):
    """Base class for web search providers."""

    name: str

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> str:
        """Run a search and return formatted results."""


class TavilyProvider(SearchProvider):
    name = "tavily"

    def __init__(self) -> None:
        from tavily import AsyncTavilyClient

        self._client = AsyncTavilyClient(api_key=os.environ["TAVILY_API_KEY"])

    async def search(self, query: str, max_results: int = 5) -> str:
        results = await self._client.search(query=query, max_results=max_results)
        return "\n\n".join(
            f"**{r['title']}**\n{r['url']}\n{r['content']}"
            for r in results.get("results", [])
        )


class SerperProvider(SearchProvider):
    name = "serper"

    def __init__(self) -> None:
        import httpx

        self._api_key = os.environ["SERPER_API_KEY"]
        self._client = httpx.AsyncClient()

    async def search(self, query: str, max_results: int = 5) -> str:
        response = await self._client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": self._api_key, "Content-Type": "application/json"},
            json={"q": query, "num": max_results},
        )
        response.raise_for_status()
        data = response.json()
        results = data.get("organic", [])[:max_results]
        return "\n\n".join(
            f"**{r.get('title', '')}**\n{r.get('link', '')}\n{r.get('snippet', '')}"
            for r in results
        )


_PROVIDERS: dict[str, type[SearchProvider]] = {
    "tavily": TavilyProvider,
    "serper": SerperProvider,
}

_provider: SearchProvider | None = None


def get_provider() -> SearchProvider:
    """Return the configured search provider (lazy singleton)."""
    global _provider
    if _provider is None:
        tool_name = os.environ.get("SEARCH_TOOL", "tavily").lower()
        cls = _PROVIDERS.get(tool_name)
        if cls is None:
            raise ValueError(
                f"Unknown SEARCH_TOOL '{tool_name}'. Options: {', '.join(_PROVIDERS)}"
            )
        _provider = cls()
        logger.info(f"Search provider initialized: {_provider.name}")
    return _provider


def get_search_tool_name() -> str:
    """Return the configured search tool name without initializing the provider."""
    return os.environ.get("SEARCH_TOOL", "tavily").lower()


async def web_search_impl(query: str) -> str:
    """Execute a web search with rate limiting and retries."""
    async with semaphore:
        provider = get_provider()
        for attempt in range(_MAX_RETRIES):
            try:
                return await provider.search(query)
            except Exception as e:
                error_detail = str(e)
                if hasattr(e, "response"):
                    try:
                        error_detail = e.response.text
                    except Exception:
                        pass
                is_rate_limit = "429" in error_detail or "rate" in error_detail.lower()
                if is_rate_limit and attempt < _MAX_RETRIES - 1:
                    delay = _RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(f"Search rate-limited, retrying in {delay}s (attempt {attempt + 1})")
                    await asyncio.sleep(delay)
                    continue
                logger.warning(f"Search failed: {error_detail}")
                return "Search failed. Try a different query."
    return "Search failed. Try a different query."
