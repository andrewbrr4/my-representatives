"""Tests for v2 pre-filter: URL dedup + snippet truncation + results ceiling."""

from research.overview.v2.prefilter import prefilter_results


def _r(url: str, snippet: str = "snippet", title: str = "t") -> dict[str, str]:
    return {"url": url, "title": title, "snippet": snippet}


def test_prefilter_dedupes_by_url_keeping_first():
    results = [
        _r("https://a.example/1", snippet="first"),
        _r("https://b.example/2", snippet="second"),
        _r("https://a.example/1", snippet="dup"),
    ]
    out = prefilter_results(results, snippet_char_cap=500, ceiling=10)
    assert [r["url"] for r in out] == ["https://a.example/1", "https://b.example/2"]
    assert out[0]["snippet"] == "first"


def test_prefilter_truncates_snippets():
    long_snippet = "x" * 2000
    out = prefilter_results([_r("https://a.example", snippet=long_snippet)], snippet_char_cap=100, ceiling=10)
    assert len(out[0]["snippet"]) == 100


def test_prefilter_applies_ceiling():
    results = [_r(f"https://a.example/{i}") for i in range(50)]
    out = prefilter_results(results, snippet_char_cap=500, ceiling=10)
    assert len(out) == 10
    assert out[0]["url"] == "https://a.example/0"


def test_prefilter_drops_entries_with_empty_url():
    results = [_r(""), _r("https://a.example")]
    out = prefilter_results(results, snippet_char_cap=500, ceiling=10)
    assert [r["url"] for r in out] == ["https://a.example"]
