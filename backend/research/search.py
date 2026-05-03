"""Shared web search tool used by all research pipelines."""

import asyncio
import logging
import os
from typing import Any

from langchain_core.tools import tool
from tavily import AsyncTavilyClient

from models import SourceLink

logger = logging.getLogger(__name__)

# Global cap on concurrent Tavily calls across the whole process. Every
# pipeline (v1/v2/v3/v4 breadth + depth, elections, issues) funnels through
# here. Tavily's paid-tier rate limit is 100 RPS, so the historical default
# of 3 was strangling throughput — especially for v3/v4 breadth fan-out and
# for parallel rep lookups. Override via TAVILY_GLOBAL_CONCURRENCY.
def _global_concurrency() -> int:
    raw = os.getenv("TAVILY_GLOBAL_CONCURRENCY")
    if not raw:
        return 20
    try:
        n = int(raw)
        return n if n > 0 else 20
    except ValueError:
        logger.warning(f"Invalid TAVILY_GLOBAL_CONCURRENCY={raw!r}; using default 20")
        return 20


_search_semaphore = asyncio.Semaphore(_global_concurrency())

_MAX_SEARCH_RETRIES = 5
_RETRY_BASE_DELAY = 5.0  # seconds, doubles each retry

# Domains to exclude from all Tavily searches. Skews the pool away from:
#   - social / video where civic-info signal is low and noise is high
#   - party-committee press releases that are 100% partisan messaging
# Tavily matches subdomains, so excluding `dscc.org` also excludes `www.dscc.org`.
# Politician self-press (e.g. schumer.senate.gov/newsroom/press-releases) is
# *not* excluded here because it'd nuke all of senate.gov/house.gov; those URL
# paths are filtered separately downstream.
_DEFAULT_EXCLUDE_DOMAINS = [
    "facebook.com",
    "m.facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "tiktok.com",
    "youtube.com",
    "m.youtube.com",
    "reddit.com",
    "dscc.org",
    "dccc.org",
    "nrsc.org",
    "nrcc.org",
    "democrats.org",
    "gop.com",
]


def _exclude_domains() -> list[str]:
    """Resolve the active exclude list, allowing env-var override.

    Set ``TAVILY_EXCLUDE_DOMAINS`` to a comma-separated list to replace
    the default (set to an empty string to disable filtering entirely).
    """
    override = os.getenv("TAVILY_EXCLUDE_DOMAINS")
    if override is None:
        return _DEFAULT_EXCLUDE_DOMAINS
    return [d.strip() for d in override.split(",") if d.strip()]


_tavily_client: AsyncTavilyClient | None = None


def _format_result(r: dict) -> str:
    """Format one Tavily result for the LangChain agent tool output."""
    header = f"**{r['title']}**\n{r['url']}"
    if r.get("published_date"):
        header += f"\nPublished: {r['published_date']}"
    return f"{header}\n{r['content']}"


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
                search_results = await tavily.search(
                    query=query,
                    max_results=5,
                    exclude_domains=_exclude_domains(),
                )
                return "\n\n".join(
                    _format_result(r) for r in search_results.get("results", [])
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


def make_accumulating_web_search() -> tuple[Any, list[SourceLink]]:
    """Build a per-invocation ``web_search`` tool that records every Tavily
    result's ``{title, url}`` (deduped, first-occurrence order) on a
    sidecar list. The tool's returned string matches ``web_search`` so the
    agent's behavior is unchanged.

    Used by pipelines that surface a 'further reading' list to the user
    (e.g. issue-stance research) — no extra Tavily calls, just keeping
    a structured reference to results we already retrieved.

    Returns ``(tool, accumulator)``. The accumulator can be handed
    directly to a summary's ``further_reading`` field.
    """
    accumulator: list[SourceLink] = []
    seen: set[str] = set()

    @tool
    async def web_search(query: str) -> str:
        """Search the web for current information about a topic. Returns relevant search results with snippets."""
        async with _search_semaphore:
            tavily = _get_tavily_client()
            for attempt in range(_MAX_SEARCH_RETRIES):
                try:
                    search_results = await tavily.search(
                        query=query,
                        max_results=5,
                        exclude_domains=_exclude_domains(),
                    )
                    raw = search_results.get("results", [])
                    for r in raw:
                        url = r.get("url", "")
                        title = r.get("title", "")
                        if not url or not title or url in seen:
                            continue
                        seen.add(url)
                        accumulator.append(SourceLink(title=title, url=url))
                    return "\n\n".join(_format_result(r) for r in raw)
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
                        logger.warning(
                            f"Search rate-limited, retrying in {delay}s (attempt {attempt + 1})"
                        )
                        await asyncio.sleep(delay)
                        continue
                    logger.warning(f"Search failed: {error_detail}")
                    return "Search failed. Try a different query."
        return "Search failed. Try a different query."

    return web_search, accumulator


async def tavily_search_raw(
    query: str, max_results: int = 5
) -> list[dict[str, str]]:
    """Run one Tavily search and return raw results as a list of dicts.

    Used by non-agent pipelines (e.g. overview v3) that execute searches
    outside the LangChain agent loop to avoid accumulating search results
    in LLM context. Returns ``[]`` on failure (caller logs + proceeds).
    Each result is ``{"title": str, "url": str, "snippet": str, "published_date": str}``
    where ``published_date`` is empty string when Tavily didn't supply one.
    """
    async with _search_semaphore:
        tavily = _get_tavily_client()
        for attempt in range(_MAX_SEARCH_RETRIES):
            try:
                search_results = await tavily.search(
                    query=query,
                    max_results=max_results,
                    exclude_domains=_exclude_domains(),
                )
                return [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("content", ""),
                        "published_date": r.get("published_date") or "",
                    }
                    for r in search_results.get("results", [])
                ]
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
                    logger.warning(f"Raw search rate-limited, retrying in {delay}s (attempt {attempt + 1})")
                    await asyncio.sleep(delay)
                    continue
                logger.warning(f"Raw search failed for query={query!r}: {error_detail}")
                return []
    return []
