"""Pre-distillation filter for v2 search results.

Operates on the raw list returned by ``tavily_search_raw`` (across all queries,
concatenated). Cheap, pure — no LLM.
"""


def prefilter_results(
    results: list[dict[str, str]],
    snippet_char_cap: int,
    ceiling: int,
) -> list[dict[str, str]]:
    """Dedupe by URL (keep first), truncate snippets, cap total count.

    Entries with an empty/missing URL are dropped. Order is preserved so
    the first N queries' results survive when the ceiling trims the tail.
    """
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for r in results:
        url = r.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        snippet = r.get("snippet", "")
        if len(snippet) > snippet_char_cap:
            snippet = snippet[:snippet_char_cap]
        out.append(
            {
                "title": r.get("title", ""),
                "url": url,
                "snippet": snippet,
            }
        )
        if len(out) >= ceiling:
            break
    return out
