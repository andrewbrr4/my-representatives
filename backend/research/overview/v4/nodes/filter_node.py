"""Filter node — heuristic dedupe + truncate + cap. No LLM."""

import logging
import os
import re

from langfuse import observe

from research.overview.v4.models import SearchResult
from research.overview.v4.state import V4State

logger = logging.getLogger(__name__)

_RESULTS_CEILING = int(os.getenv("OVERVIEW_V4_RESULTS_CEILING", "60"))
_SNIPPET_CHAR_CAP = int(os.getenv("OVERVIEW_V4_SNIPPET_CHAR_CAP", "800"))
_SNIPPET_DEDUPE_PREFIX = 200

_WHITESPACE_RUN = re.compile(r"\s+")


def _snippet_dedupe_key(s: str) -> str:
    """Normalized prefix used to detect AP-wire-style republished content
    (different URLs, identical snippet bodies). Empty → no dedupe."""
    if not s:
        return ""
    cleaned = _WHITESPACE_RUN.sub(" ", s.strip().lower())
    return cleaned[:_SNIPPET_DEDUPE_PREFIX]

# Politician self-press / committee press releases. Tavily can only
# filter by domain; these patterns let us keep legit `*.senate.gov` /
# `*.house.gov` content (voting records, committee transcripts) while
# dropping the partisan press-release subpaths that leak through.
_OFFICIAL_GOV_SUFFIXES = (".senate.gov", ".house.gov")
_PRESS_PATH_TOKENS = ("/newsroom/", "/news/press", "/press-release", "/press_release")


def _is_self_press(url: str) -> bool:
    if not url:
        return False
    u = url.lower()
    has_official = any(d in u for d in _OFFICIAL_GOV_SUFFIXES)
    has_press_path = any(t in u for t in _PRESS_PATH_TOKENS)
    return has_official and has_press_path


@observe(name="v4-filter")
async def filter_node(state: V4State) -> dict:
    """Dedupe by URL + snippet, drop self-press URLs, truncate snippets, cap total."""
    raw = state["raw_results"]
    seen_urls: set[str] = set()
    seen_snippets: set[str] = set()
    out: list[SearchResult] = []
    self_press_dropped = 0
    snippet_dupes_dropped = 0
    for r in raw:
        if not r.url or r.url in seen_urls:
            continue
        seen_urls.add(r.url)
        if _is_self_press(r.url):
            self_press_dropped += 1
            continue
        key = _snippet_dedupe_key(r.snippet)
        if key and key in seen_snippets:
            snippet_dupes_dropped += 1
            continue
        if key:
            seen_snippets.add(key)
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
    logger.info(
        f"[v4] Filter: {len(raw)} → {len(out)} results "
        f"(dropped {self_press_dropped} self-press, {snippet_dupes_dropped} snippet-dupes)"
    )
    return {"filtered_results": out}
