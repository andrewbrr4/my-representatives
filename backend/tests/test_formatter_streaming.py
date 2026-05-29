import asyncio

from research.overview.models import SearchResult
from research.overview.nodes.formatter import (
    _consume_stream,
    _handle_line,
    _min_bullets,
    _streaming_enabled,
)


def _pool():
    return {
        "https://a.com": SearchResult(
            url="https://a.com", title="A title", snippet="s", published_date="2025-01-01"
        ),
        "https://b.com": SearchResult(
            url="https://b.com", title="B title", snippet="s"
        ),
    }


async def _gen(chunks):
    for c in chunks:
        yield c


def test_handle_line_parses_valid_object():
    bullets, citations, url_to_n = [], [], {}

    async def run():
        return await _handle_line(
            '{"text": "Voted yes on the bill", "sources": ["https://a.com"]}',
            pool_by_url=_pool(),
            bullets=bullets,
            citations=citations,
            url_to_n=url_to_n,
            sources=[],
            store=None,
            research_id=None,
        )

    added = asyncio.run(run())
    assert added is True
    assert bullets == ["Voted yes on the bill [1]"]
    assert len(citations) == 1
    assert citations[0].url == "https://a.com"


def test_handle_line_skips_blank_and_malformed():
    bullets, citations, url_to_n = [], [], {}

    async def run():
        for line in ["", "   ", "not json", '{"text": 5, "sources": []}', '["array"]']:
            await _handle_line(
                line,
                pool_by_url=_pool(),
                bullets=bullets,
                citations=citations,
                url_to_n=url_to_n,
                sources=[],
                store=None,
                research_id=None,
            )

    asyncio.run(run())
    assert bullets == []
    assert citations == []


def test_handle_line_drops_unknown_urls():
    bullets, citations, url_to_n = [], [], {}

    async def run():
        await _handle_line(
            '{"text": "Claim", "sources": ["https://hallucinated.com", "https://a.com"]}',
            pool_by_url=_pool(),
            bullets=bullets,
            citations=citations,
            url_to_n=url_to_n,
            sources=[],
            store=None,
            research_id=None,
        )

    asyncio.run(run())
    # Only the in-pool URL becomes a citation; marker reflects only [1].
    assert bullets == ["Claim [1]"]
    assert [c.url for c in citations] == ["https://a.com"]


def test_handle_line_dedupes_urls_across_bullets():
    bullets, citations, url_to_n = [], [], {}

    async def run():
        await _handle_line(
            '{"text": "First", "sources": ["https://a.com"]}',
            pool_by_url=_pool(), bullets=bullets, citations=citations,
            url_to_n=url_to_n, sources=[], store=None, research_id=None,
        )
        await _handle_line(
            '{"text": "Second", "sources": ["https://a.com", "https://b.com"]}',
            pool_by_url=_pool(), bullets=bullets, citations=citations,
            url_to_n=url_to_n, sources=[], store=None, research_id=None,
        )

    asyncio.run(run())
    assert bullets == ["First [1]", "Second [1][2]"]
    assert len(citations) == 2  # a.com reused as [1], b.com added as [2]


def test_consume_stream_reassembles_split_chunks():
    # A single JSON line delivered across two chunks, no trailing newline.
    chunks = ['{"text": "Hel', 'lo world", "sources": ["https://a.com"]}']

    async def run():
        return await _consume_stream(
            _gen(chunks),
            pool_by_url=_pool(),
            sources=[],
            store=None,
            research_id=None,
        )

    summary = asyncio.run(run())
    assert summary.bullets == ["Hello world [1]"]


def test_consume_stream_handles_multiple_lines_in_one_chunk():
    chunk = (
        '{"text": "One", "sources": ["https://a.com"]}\n'
        '{"text": "Two", "sources": ["https://b.com"]}\n'
    )

    async def run():
        return await _consume_stream(
            _gen([chunk]),
            pool_by_url=_pool(),
            sources=[],
            store=None,
            research_id=None,
        )

    summary = asyncio.run(run())
    assert summary.bullets == ["One [1]", "Two [2]"]


def test_consume_stream_writes_partials_to_store():
    from store.research_store import InMemoryResearchStore
    from research.overview.models import ResearchSummary

    store = InMemoryResearchStore()

    async def run():
        await store.create("rid", total_sections=1, summary=ResearchSummary())
        await _consume_stream(
            _gen(['{"text": "One", "sources": ["https://a.com"]}\n']),
            pool_by_url=_pool(),
            sources=[],
            store=store,
            research_id="rid",
        )
        return await store.get("rid")

    task = asyncio.run(run())
    assert task.summary.bullets == ["One [1]"]
    assert task.status == "in_progress"


def test_streaming_enabled_default_true(monkeypatch):
    monkeypatch.delenv("OVERVIEW_V4_FORMATTER_STREAMING", raising=False)
    assert _streaming_enabled() is True
    monkeypatch.setenv("OVERVIEW_V4_FORMATTER_STREAMING", "false")
    assert _streaming_enabled() is False


def test_min_bullets_default(monkeypatch):
    monkeypatch.delenv("OVERVIEW_V4_FORMATTER_MIN_BULLETS", raising=False)
    assert _min_bullets() == 3
