"""Breadth-search node — parallel Tavily fan-out, no LLM in the loop."""

import asyncio
import logging
import os

from langfuse import observe

from research.overview.v4.models import SearchResult
from research.overview.v4.state import V4State
from research.search import tavily_search_raw

logger = logging.getLogger(__name__)

_RESULTS_PER_QUERY = int(os.getenv("OVERVIEW_V4_RESULTS_PER_QUERY", "5"))
_SEARCH_CONCURRENCY = int(os.getenv("OVERVIEW_V4_SEARCH_CONCURRENCY", "5"))


@observe(name="v4-breadth-search")
async def breadth_search(state: V4State) -> dict:
    """Run all queries in parallel against Tavily, bounded by a semaphore."""
    queries = state["queries"]
    sem = asyncio.Semaphore(_SEARCH_CONCURRENCY)

    async def _run_one(q: str) -> list[dict[str, str]]:
        async with sem:
            return await tavily_search_raw(q, max_results=_RESULTS_PER_QUERY)

    per_query = await asyncio.gather(*(_run_one(q) for q in queries))
    flat: list[SearchResult] = []
    successful = 0
    for results in per_query:
        if results:
            successful += 1
            for r in results:
                flat.append(
                    SearchResult(
                        url=r.get("url", ""),
                        title=r.get("title", ""),
                        snippet=r.get("snippet", ""),
                        published_date=r.get("published_date", "") or "",
                    )
                )
    logger.info(
        f"[v4] Breadth search: {successful}/{len(queries)} queries returned "
        f"results; {len(flat)} total"
    )
    return {"raw_results": flat}
