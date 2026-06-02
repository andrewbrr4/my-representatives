"""Behavior lock-in for the shared Tavily search core (research/search.py).

These exercise the three public tools through a fake Tavily client (set on the
module-level client global, so no API key or network is needed). The point is to
pin the contract that survived the dedup refactor: success formatting, the
failure sentinel vs. empty-success distinction, accumulator dedup, the raw-dict
shape, and rate-limit retry.
"""

import asyncio

import research.search as search


class _FakeTavily:
    """Async Tavily stand-in. Returns canned results, or raises a scripted
    sequence of exceptions (one per call) before succeeding."""

    def __init__(self, results=None, raises=None):
        self._results = results if results is not None else []
        self._raises = list(raises or [])
        self.calls = 0

    async def search(self, query, max_results, exclude_domains):
        self.calls += 1
        if self._raises:
            exc = self._raises.pop(0)
            raise exc
        return {"results": self._results}


def _install(monkeypatch_results=None, raises=None):
    fake = _FakeTavily(results=monkeypatch_results, raises=raises)
    search._tavily_client = fake
    return fake


def _reset():
    search._tavily_client = None


_RESULTS = [
    {"title": "A", "url": "https://a.com", "content": "alpha", "published_date": "2026-01-01"},
    {"title": "B", "url": "https://b.com", "content": "beta", "published_date": ""},
]


def test_web_search_formats_results():
    _install(_RESULTS)
    try:
        out = asyncio.run(search.web_search.ainvoke({"query": "q"}))
    finally:
        _reset()
    assert "**A**" in out and "https://a.com" in out and "alpha" in out
    assert "Published: 2026-01-01" in out
    assert "**B**" in out


def test_web_search_returns_sentinel_on_failure():
    _install(raises=[RuntimeError("boom")])
    try:
        out = asyncio.run(search.web_search.ainvoke({"query": "q"}))
    finally:
        _reset()
    assert out == search._SEARCH_FAILED_MSG


def test_empty_success_is_not_failure_sentinel():
    _install([])
    try:
        out = asyncio.run(search.web_search.ainvoke({"query": "q"}))
    finally:
        _reset()
    assert out == ""  # empty join, not the failure message


def test_accumulating_dedupes_by_url():
    dup = _RESULTS + [{"title": "A again", "url": "https://a.com", "content": "x", "published_date": ""}]
    _install(dup)
    tool, acc = search.make_accumulating_web_search()
    try:
        asyncio.run(tool.ainvoke({"query": "q"}))
    finally:
        _reset()
    assert [s.url for s in acc] == ["https://a.com", "https://b.com"]


def test_raw_maps_shape_and_empty_on_failure():
    _install(_RESULTS)
    try:
        rows = asyncio.run(search.tavily_search_raw("q"))
    finally:
        _reset()
    assert rows[0] == {"title": "A", "url": "https://a.com", "snippet": "alpha", "published_date": "2026-01-01"}
    assert rows[1]["published_date"] == ""  # falsy date normalized to ""

    _install(raises=[RuntimeError("boom")])
    try:
        rows = asyncio.run(search.tavily_search_raw("q"))
    finally:
        _reset()
    assert rows == []


def test_retries_on_rate_limit_then_succeeds(monkeypatch):
    async def _no_sleep(_delay):
        return None

    monkeypatch.setattr(search.asyncio, "sleep", _no_sleep)
    fake = _install(_RESULTS, raises=[Exception("HTTP 429 too many requests")])
    try:
        out = asyncio.run(search.web_search.ainvoke({"query": "q"}))
    finally:
        _reset()
    assert fake.calls == 2  # one 429, one success
    assert "**A**" in out
