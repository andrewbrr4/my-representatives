"""Filter node — heuristic dedupe + truncate + cap. No LLM."""

import logging
import os

from research.overview.v4.models import SearchResult
from research.overview.v4.state import V4State

logger = logging.getLogger(__name__)

_RESULTS_CEILING = int(os.getenv("OVERVIEW_V4_RESULTS_CEILING", "60"))
_SNIPPET_CHAR_CAP = int(os.getenv("OVERVIEW_V4_SNIPPET_CHAR_CAP", "800"))


async def filter_node(state: V4State) -> dict:
    """Dedupe by URL (keep first), truncate snippets, cap total count."""
    raw = state["raw_results"]
    seen: set[str] = set()
    out: list[SearchResult] = []
    for r in raw:
        if not r.url or r.url in seen:
            continue
        seen.add(r.url)
        snippet = r.snippet
        if len(snippet) > _SNIPPET_CHAR_CAP:
            snippet = snippet[:_SNIPPET_CHAR_CAP]
        out.append(
            SearchResult(
                url=r.url,
                title=r.title,
                snippet=snippet,
                published_date=r.published_date,
            )
        )
        if len(out) >= _RESULTS_CEILING:
            break
    logger.info(f"[v4] Filter: {len(raw)} → {len(out)} results")
    return {"filtered_results": out}
