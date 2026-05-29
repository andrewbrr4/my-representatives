# Loading Progress + Fun Facts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** While a rep's AI overview is researched, show a per-node progress bar and a DB-served fun-facts carousel; then stream the formatter's bullets one-by-one as they land.

**Architecture:** Each v4 LangGraph node reports a `(label, pct)` step to the in-memory research store; the existing 2s poll surfaces it via a new `progress` field. The formatter switches from a blocking structured-output call to NDJSON line streaming, writing each parsed bullet to the store via `update_partial()`. Facts live in a Postgres `facts` table behind `GET /api/facts`, cached client-side. The frontend loading state renders progress + facts until the first bullet arrives, then flips to a live bullets view with a trailer skeleton.

**Tech Stack:** FastAPI / Python 3.13 / asyncpg / LangGraph / LangChain (`ChatAnthropic`); React + TypeScript + Vite + TanStack Query v5 + Tailwind + shadcn/ui. Backend tests: `pytest` (run inside the `my-reps` conda env), using `asyncio.run()` for async functions (no `pytest-asyncio` dependency).

**Spec:** [docs/superpowers/specs/2026-05-29-loading-progress-and-facts-design.md](../specs/2026-05-29-loading-progress-and-facts-design.md)

**Conventions:**
- All backend commands run from `backend/` inside the conda env: prefix with `conda run -n my-reps`.
- Backend uses bare-module imports (uvicorn runs from `backend/`), so tests run from `backend/` with `pythonpath = .`.
- Frontend commands run from `frontend/`.

---

## Task 1: Backend test scaffolding

**Files:**
- Create: `backend/pytest.ini`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_scaffold.py`

- [ ] **Step 1: Create the pytest config**

Create `backend/pytest.ini`:

```ini
[pytest]
pythonpath = .
testpaths = tests
python_files = test_*.py
```

- [ ] **Step 2: Create the tests package marker**

Create `backend/tests/__init__.py` (empty file):

```python
```

- [ ] **Step 3: Write a smoke test that imports a bare module**

Create `backend/tests/test_scaffold.py`:

```python
def test_imports_bare_module():
    from store.research_store import InMemoryResearchStore

    assert InMemoryResearchStore is not None
```

- [ ] **Step 4: Run it**

Run: `cd backend && conda run -n my-reps pytest tests/test_scaffold.py -v`
Expected: PASS (1 passed). Confirms `pythonpath = .` resolves bare imports.

- [ ] **Step 5: Commit**

```bash
git add backend/pytest.ini backend/tests/__init__.py backend/tests/test_scaffold.py
git commit -m "test: add backend pytest scaffolding"
```

---

## Task 2: Store progress fields + `update_progress` + `update_partial`

**Files:**
- Modify: `backend/store/research_store.py`
- Test: `backend/tests/test_research_store_progress.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_research_store_progress.py`:

```python
import asyncio

from pydantic import BaseModel

from store.research_store import InMemoryResearchStore


class _Summary(BaseModel):
    bullets: list[str] = []


def test_update_progress_sets_fields_and_transitions():
    store = InMemoryResearchStore()

    async def run():
        await store.create("r1", total_sections=1, summary=_Summary())
        await store.update_progress("r1", 20, "Searching the web")
        return await store.get("r1")

    task = asyncio.run(run())
    assert task.progress_pct == 20
    assert task.progress_label == "Searching the web"
    assert task.status == "in_progress"  # transitioned from pending


def test_update_progress_missing_task_is_noop():
    store = InMemoryResearchStore()

    async def run():
        await store.update_progress("nope", 50, "x")  # must not raise

    asyncio.run(run())  # no exception = pass


def test_update_partial_replaces_summary_without_completing():
    store = InMemoryResearchStore()

    async def run():
        await store.create("r2", total_sections=1, summary=_Summary())
        await store.update_partial("r2", _Summary(bullets=["one"]))
        return await store.get("r2")

    task = asyncio.run(run())
    assert task.summary.bullets == ["one"]
    assert task.status == "in_progress"  # NOT complete
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && conda run -n my-reps pytest tests/test_research_store_progress.py -v`
Expected: FAIL (`AttributeError: 'ResearchTask' object has no attribute 'progress_pct'` / `update_progress` missing).

- [ ] **Step 3: Add the fields**

In `backend/store/research_store.py`, modify the `ResearchTask` dataclass:

```python
@dataclass
class ResearchTask:
    research_id: str
    total_sections: int = 5  # default for rep research
    status: str = "pending"  # "pending" | "in_progress" | "complete" | "failed"
    summary: PydanticBaseModel | None = None
    completed_sections: int = 0
    created_at: float = field(default_factory=time.time)
    progress_pct: int = 0
    progress_label: str = "Getting started"
```

- [ ] **Step 4: Add the two methods**

In `backend/store/research_store.py`, add these methods to `InMemoryResearchStore` (place them right after `complete_section`):

```python
    async def update_progress(self, research_id: str, pct: int, label: str) -> None:
        """Update the per-node progress shown while research is in flight."""
        async with self._lock:
            task = self._tasks.get(research_id)
            if not task:
                return
            task.progress_pct = pct
            task.progress_label = label
            if task.status == "pending":
                task.status = "in_progress"

    async def update_partial(self, research_id: str, summary: PydanticBaseModel) -> None:
        """Replace the in-progress summary with a newer partial (streaming bullets).

        Sets status to in_progress if pending. Does NOT mark complete — the
        caller invokes complete() at the end (or fail() on error).
        """
        async with self._lock:
            task = self._tasks.get(research_id)
            if not task:
                return
            task.summary = summary
            if task.status == "pending":
                task.status = "in_progress"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && conda run -n my-reps pytest tests/test_research_store_progress.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/store/research_store.py backend/tests/test_research_store_progress.py
git commit -m "feat(store): add progress fields, update_progress, update_partial"
```

---

## Task 3: Progress registry + `report_step`

**Files:**
- Create: `backend/research/overview/progress.py`
- Test: `backend/tests/test_progress.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_progress.py`:

```python
import asyncio

from pydantic import BaseModel

from research.overview.progress import PROGRESS_STEPS, report_step
from store.research_store import InMemoryResearchStore


class _Summary(BaseModel):
    bullets: list[str] = []


def test_report_step_writes_label_and_pct():
    store = InMemoryResearchStore()

    async def run():
        await store.create("r1", total_sections=1, summary=_Summary())
        await report_step({"store": store, "research_id": "r1"}, "breadth_search")
        return await store.get("r1")

    task = asyncio.run(run())
    assert task.progress_label == "Searching the web"
    assert task.progress_pct == 20


def test_report_step_noops_without_store():
    async def run():
        # No store / research_id in state -> must not raise.
        await report_step({}, "breadth_search")

    asyncio.run(run())


def test_all_pipeline_node_keys_present():
    keys = {key for key, _label, _pct in PROGRESS_STEPS}
    assert keys == {
        "query_generator",
        "breadth_search",
        "filter",
        "research_agent",
        "formatter",
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && conda run -n my-reps pytest tests/test_progress.py -v`
Expected: FAIL (`ModuleNotFoundError: research.overview.progress`).

- [ ] **Step 3: Create the registry module**

Create `backend/research/overview/progress.py`:

```python
"""Per-node progress reporting for the v4 overview pipeline.

Single source of truth for the step -> (label, percent) mapping shown in
the frontend progress bar while research is in flight. Each node calls
``report_step(state, "<key>")`` as its first statement. The percentages are
first-draft, informed by V4_PERFORMANCE latency notes (breadth /
research_agent / formatter dominate) and are trivially tunable here.
"""

import logging

from research.overview.state import V4State

logger = logging.getLogger(__name__)

# (node_key, label shown while running, percent shown while running)
PROGRESS_STEPS: list[tuple[str, str, int]] = [
    ("query_generator", "Planning what to research", 5),
    ("breadth_search", "Searching the web", 20),
    ("filter", "Sorting through sources", 45),
    ("research_agent", "Digging into the details", 55),
    ("formatter", "Writing the summary", 85),
]

_LOOKUP: dict[str, tuple[str, int]] = {
    key: (label, pct) for key, label, pct in PROGRESS_STEPS
}


async def report_step(state: V4State, key: str) -> None:
    """Report the current pipeline step to the store, if plumbed.

    No-ops when ``store`` / ``research_id`` are absent from state (e.g. unit
    tests invoking nodes directly), so nodes can call it unconditionally.
    """
    store = state.get("store")
    research_id = state.get("research_id")
    if store is None or research_id is None:
        return
    label, pct = _LOOKUP[key]
    await store.update_progress(research_id, pct, label)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && conda run -n my-reps pytest tests/test_progress.py -v`
Expected: PASS (3 passed).

> Note: `report_step` imports `V4State` from `research.overview.state`, which is extended in Task 4. The import already works today (`V4State` exists); Task 4 only adds optional fields.

- [ ] **Step 5: Commit**

```bash
git add backend/research/overview/progress.py backend/tests/test_progress.py
git commit -m "feat(overview): add progress step registry and report_step"
```

---

## Task 4: Plumb `store` + `research_id` into `V4State` and the pipeline

**Files:**
- Modify: `backend/research/overview/state.py`
- Modify: `backend/research/overview/pipeline.py`

- [ ] **Step 1: Add optional state fields**

In `backend/research/overview/state.py`, update the imports and `V4State`:

Change the typing import line:

```python
from typing import Annotated, TypedDict
```

to:

```python
from typing import Annotated, NotRequired, TypedDict
```

Add this import near the other imports (after `from research.usage import UsageStats`):

```python
from store.research_store import InMemoryResearchStore
```

Add these two fields inside `class V4State(TypedDict, total=False):` (after `usage_log`):

```python
    # Plumbed from the entrypoint for progress reporting + formatter streaming.
    # Other nodes ignore them.
    store: NotRequired[InMemoryResearchStore]
    research_id: NotRequired[str]
```

- [ ] **Step 2: Populate them in the entrypoint**

In `backend/research/overview/pipeline.py`, replace this block inside `research_representative`:

```python
    initial: V4State = {"rep": rep, "usage_log": []}
    try:
        result = await pipeline_graph.ainvoke(
            initial,
            config={"run_name": f"v4:pipeline:{rep.name}"},
        )
```

with:

```python
    initial: V4State = {"rep": rep, "usage_log": []}
    if store is not None and research_id is not None:
        initial["store"] = store
        initial["research_id"] = research_id
    try:
        result = await pipeline_graph.ainvoke(
            initial,
            config={"run_name": f"v4:pipeline:{rep.name}"},
        )
```

- [ ] **Step 3: Verify imports resolve (no circular import)**

Run: `cd backend && conda run -n my-reps python -c "import research.overview.pipeline; import research.overview.progress; print('ok')"`
Expected: prints `ok` (confirms `state` -> `store.research_store` import is acyclic).

- [ ] **Step 4: Run the existing suite to confirm nothing broke**

Run: `cd backend && conda run -n my-reps pytest tests/ -v`
Expected: PASS (all prior tests still green).

- [ ] **Step 5: Commit**

```bash
git add backend/research/overview/state.py backend/research/overview/pipeline.py
git commit -m "feat(overview): plumb store + research_id into V4State"
```

---

## Task 5: Call `report_step` at the entry of each pipeline node

**Files:**
- Modify: `backend/research/overview/nodes/query_generator.py`
- Modify: `backend/research/overview/nodes/breadth_search.py`
- Modify: `backend/research/overview/nodes/filter_node.py`
- Modify: `backend/research/overview/nodes/research_agent.py`

> The `formatter` node's `report_step` call is added in Task 7 as part of its dispatch split.

- [ ] **Step 1: Add the import + call to `query_generator`**

In `backend/research/overview/nodes/query_generator.py`, add this import near the top (with the other `research.overview` imports):

```python
from research.overview.progress import report_step
```

Find the node function (the one decorated with `@observe` that takes `state` — its name is the value wired in `pipeline.py` as `query_generator`). Add as its **first statement** inside the function body:

```python
    await report_step(state, "query_generator")
```

- [ ] **Step 2: Repeat for `breadth_search`**

In `backend/research/overview/nodes/breadth_search.py`, add the import:

```python
from research.overview.progress import report_step
```

and as the first statement of the node function:

```python
    await report_step(state, "breadth_search")
```

- [ ] **Step 3: Repeat for `filter_node`**

In `backend/research/overview/nodes/filter_node.py`, add the import:

```python
from research.overview.progress import report_step
```

and as the first statement of the `filter_node` function:

```python
    await report_step(state, "filter")
```

- [ ] **Step 4: Repeat for `research_agent`**

In `backend/research/overview/nodes/research_agent.py`, add the import:

```python
from research.overview.progress import report_step
```

and as the first statement of `research_agent_node`:

```python
    await report_step(state, "research_agent")
```

- [ ] **Step 5: Verify imports**

Run: `cd backend && conda run -n my-reps python -c "import research.overview.pipeline; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 6: Commit**

```bash
git add backend/research/overview/nodes/query_generator.py backend/research/overview/nodes/breadth_search.py backend/research/overview/nodes/filter_node.py backend/research/overview/nodes/research_agent.py
git commit -m "feat(overview): report progress at each node entry"
```

---

## Task 6: Formatter streaming helpers (`_handle_line`, `_consume_stream`, gates)

**Files:**
- Modify: `backend/research/overview/nodes/formatter.py`
- Test: `backend/tests/test_formatter_streaming.py`

This task adds the streaming helper functions and tests them. The dispatch wiring (Task 7) comes next.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_formatter_streaming.py`:

```python
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
    # A single JSON line delivered across three chunks, no trailing newline.
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && conda run -n my-reps pytest tests/test_formatter_streaming.py -v`
Expected: FAIL (`ImportError: cannot import name '_handle_line'`).

- [ ] **Step 3: Add the helpers + gates to `formatter.py`**

In `backend/research/overview/nodes/formatter.py`:

Add `import json` at the top (with the other stdlib imports), and add this import:

```python
from store.research_store import InMemoryResearchStore
```

Add these functions at module level (place them after `_attach_markers`, before the `@observe`-decorated `formatter`):

```python
def _streaming_enabled() -> bool:
    """Default ON — streaming is the intended formatter experience. Flip the
    env var to ``false`` to fall back to the structured-output path."""
    return os.getenv("OVERVIEW_V4_FORMATTER_STREAMING", "true").strip().lower() in (
        "1", "true", "yes", "on"
    )


def _min_bullets() -> int:
    return int(os.getenv("OVERVIEW_V4_FORMATTER_MIN_BULLETS", "3"))


async def _handle_line(
    line: str,
    *,
    pool_by_url: dict[str, SearchResult],
    bullets: list[str],
    citations: list[Citation],
    url_to_n: dict[str, int],
    sources: list[SourceLink],
    store: InMemoryResearchStore | None,
    research_id: str | None,
) -> bool:
    """Parse one NDJSON line, append a bullet + citations, write a partial.

    Mutates ``bullets`` / ``citations`` / ``url_to_n`` in place. Returns True
    if a bullet was appended, False if the line was skipped (blank, malformed
    JSON, or wrong shape). URLs not in ``pool_by_url`` are dropped (logged) —
    same hallucination-drop philosophy as the structured path.
    """
    line = line.strip()
    if not line:
        return False
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        logger.warning(f"[v4] formatter stream: skipping malformed line: {line[:120]}")
        return False
    if not isinstance(obj, dict):
        logger.warning("[v4] formatter stream: skipping non-object line")
        return False
    text = obj.get("text")
    srcs = obj.get("sources")
    if not isinstance(text, str) or not text.strip() or not isinstance(srcs, list):
        logger.warning("[v4] formatter stream: skipping bad-shape line")
        return False

    for url in srcs:
        if not isinstance(url, str) or not url or url in url_to_n:
            continue
        sr = pool_by_url.get(url)
        if sr is None:
            logger.warning(f"[v4] formatter stream cited URL not in pool, dropping: {url}")
            continue
        citations.append(
            Citation(title=sr.title or url, url=url, published_date=sr.published_date or None)
        )
        url_to_n[url] = len(citations)  # 1-indexed N

    ns = sorted({url_to_n[u] for u in srcs if isinstance(u, str) and u in url_to_n})
    marker = "".join(f"[{n}]" for n in ns)
    text = text.strip()
    bullets.append(f"{text} {marker}".rstrip() if marker else text)

    if store is not None and research_id is not None:
        await store.update_partial(
            research_id,
            ResearchSummary(
                bullets=list(bullets), citations=list(citations), sources=sources
            ),
        )
    return True


async def _consume_stream(
    content_iter,
    *,
    pool_by_url: dict[str, SearchResult],
    sources: list[SourceLink],
    store: InMemoryResearchStore | None,
    research_id: str | None,
) -> ResearchSummary:
    """Drive the NDJSON line loop over an async iterator of content strings.

    Buffers partial lines across chunks; drains a trailing unterminated line
    at the end. Returns the final ResearchSummary.
    """
    line_buffer = ""
    bullets: list[str] = []
    citations: list[Citation] = []
    url_to_n: dict[str, int] = {}
    n_chunks = 0

    async for content in content_iter:
        n_chunks += 1
        line_buffer += content if isinstance(content, str) else str(content)
        while "\n" in line_buffer:
            line, line_buffer = line_buffer.split("\n", 1)
            await _handle_line(
                line, pool_by_url=pool_by_url, bullets=bullets, citations=citations,
                url_to_n=url_to_n, sources=sources, store=store, research_id=research_id,
            )
    if line_buffer.strip():
        await _handle_line(
            line_buffer, pool_by_url=pool_by_url, bullets=bullets, citations=citations,
            url_to_n=url_to_n, sources=sources, store=store, research_id=research_id,
        )

    logger.info(f"[v4] Formatter streamed {len(bullets)} bullets in {n_chunks} chunks")
    return ResearchSummary(bullets=bullets, citations=citations, sources=sources)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && conda run -n my-reps pytest tests/test_formatter_streaming.py -v`
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/research/overview/nodes/formatter.py backend/tests/test_formatter_streaming.py
git commit -m "feat(formatter): add NDJSON streaming helpers + gates"
```

---

## Task 7: Split `formatter` into streaming/structured dispatch

**Files:**
- Modify: `backend/research/overview/nodes/formatter.py`
- Test: `backend/tests/test_formatter_dispatch.py`

- [ ] **Step 1: Write failing dispatch tests**

Create `backend/tests/test_formatter_dispatch.py`:

```python
import asyncio

import research.overview.nodes.formatter as fmt


def test_dispatch_picks_streaming_when_enabled(monkeypatch):
    calls = []

    async def fake_streaming(state):
        calls.append("streaming")
        return {"summary": None, "usage_log": []}

    async def fake_structured(state):
        calls.append("structured")
        return {"summary": None, "usage_log": []}

    monkeypatch.setattr(fmt, "_streaming_enabled", lambda: True)
    monkeypatch.setattr(fmt, "_formatter_streaming", fake_streaming)
    monkeypatch.setattr(fmt, "_formatter_structured", fake_structured)

    asyncio.run(fmt.formatter({"rep": None}))
    assert calls == ["streaming"]


def test_dispatch_picks_structured_when_disabled(monkeypatch):
    calls = []

    async def fake_streaming(state):
        calls.append("streaming")
        return {"summary": None, "usage_log": []}

    async def fake_structured(state):
        calls.append("structured")
        return {"summary": None, "usage_log": []}

    monkeypatch.setattr(fmt, "_streaming_enabled", lambda: False)
    monkeypatch.setattr(fmt, "_formatter_streaming", fake_streaming)
    monkeypatch.setattr(fmt, "_formatter_structured", fake_structured)

    asyncio.run(fmt.formatter({"rep": None}))
    assert calls == ["structured"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && conda run -n my-reps pytest tests/test_formatter_dispatch.py -v`
Expected: FAIL (`AttributeError: module ... has no attribute '_formatter_streaming'`).

- [ ] **Step 3: Rename the existing node body to `_formatter_structured`**

In `backend/research/overview/nodes/formatter.py`, find the current node:

```python
@observe(name="v4-formatter")
async def formatter(state: V4State) -> dict:
    """Format breadth + depth search results into bullets; assemble
    citations in python."""
    rep = state["rep"]
```

Change it to (remove the `@observe` decorator from this function — it moves to the new dispatch — and rename):

```python
async def _formatter_structured(state: V4State) -> dict:
    """Format breadth + depth search results into bullets; assemble
    citations in python. (Structured-output path — the streaming fallback.)"""
    rep = state["rep"]
```

Leave the rest of that function body unchanged.

- [ ] **Step 4: Add the streaming node + dispatch**

In `backend/research/overview/nodes/formatter.py`, add the import for `report_step` near the top:

```python
from research.overview.progress import report_step
```

Add these functions (place `_formatter_streaming` after `_consume_stream` from Task 6, and `formatter` as the public dispatch — put `formatter` last in the file):

```python
async def _formatter_streaming(state: V4State) -> dict:
    """NDJSON line-streaming formatter: emits bullets to the store as they
    land via update_partial(). Falls back to RuntimeError (-> task fail) if
    fewer than _min_bullets() valid bullets are produced."""
    rep = state["rep"]
    filtered = state.get("filtered_results") or []
    depth = state.get("depth_search_results") or []
    store = state.get("store")
    research_id = state.get("research_id")

    show_sources = _show_sources_enabled()
    if show_sources:
        before = len(depth)
        depth = _dedupe_depth_against_breadth(filtered, depth)
        logger.info(
            f"[v4] Formatter dedupe (show-sources on): depth {before} -> {len(depth)}"
        )

    breadth_block = _format_breadth_block(filtered)
    depth_block = _format_depth_block(depth)
    pool = filtered + depth
    pool_by_url = {r.url: r for r in pool if r.url}
    sources = _build_sources(pool) if show_sources else []

    langfuse_handler = CallbackHandler()
    usage_tracker = UsageTracker()
    model = ChatAnthropic(
        model=_model_id(),
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    )

    system_template = Template((_PROMPTS_DIR / "formatter_system.txt").read_text())
    user_template = Template((_PROMPTS_DIR / "formatter_user_streaming.txt").read_text())
    system_prompt = system_template.substitute(current_date=date.today().isoformat())
    user_prompt = user_template.substitute(
        name=rep.name,
        office=rep.office,
        breadth_block=breadth_block,
        depth_block=depth_block,
    )

    async def _content_iter():
        async for chunk in model.astream(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
            config={
                "callbacks": [langfuse_handler, usage_tracker],
                "run_name": f"v4:formatter:{rep.name}",
            },
        ):
            yield chunk.content

    summary = await _consume_stream(
        _content_iter(),
        pool_by_url=pool_by_url,
        sources=sources,
        store=store,
        research_id=research_id,
    )

    if len(summary.bullets) < _min_bullets():
        raise RuntimeError(
            f"formatter produced too few valid bullets: {len(summary.bullets)}"
        )

    logger.info(
        f"[v4] Formatter (streaming) for {rep.name}: {len(summary.bullets)} bullets / "
        f"{len(summary.citations)} citations / {len(summary.sources)} sources"
    )
    return {"summary": summary, "usage_log": [usage_tracker.stats]}


@observe(name="v4-formatter")
async def formatter(state: V4State) -> dict:
    """Dispatch: report the formatter step, then stream or use structured output."""
    await report_step(state, "formatter")
    if _streaming_enabled():
        return await _formatter_streaming(state)
    return await _formatter_structured(state)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && conda run -n my-reps pytest tests/test_formatter_dispatch.py tests/test_formatter_streaming.py -v`
Expected: PASS (11 passed).

- [ ] **Step 6: Confirm the pipeline still imports**

Run: `cd backend && conda run -n my-reps python -c "import research.overview.pipeline; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 7: Commit**

```bash
git add backend/research/overview/nodes/formatter.py backend/tests/test_formatter_dispatch.py
git commit -m "feat(formatter): dispatch between streaming and structured paths"
```

---

## Task 8: Streaming prompt file

**Files:**
- Create: `backend/research/overview/prompts/formatter_user_streaming.txt`

- [ ] **Step 1: Read the existing user prompt**

Run: `cd backend && cat research/overview/prompts/formatter_user.txt`
Expected: shows the current prompt (template vars `$name`, `$office`, `$breadth_block`, `$depth_block`, and a trailing wire-shape reminder for the structured `bullet_texts`/`bullet_sources` shape).

- [ ] **Step 2: Create the streaming variant**

Create `backend/research/overview/prompts/formatter_user_streaming.txt` as a copy of `formatter_user.txt` with everything identical **except** the trailing OUTPUT FORMAT block, which becomes:

```
**OUTPUT FORMAT (CRITICAL):**
Emit one bullet per line as a single JSON object on each line. No outer array, no markdown, no commentary, no leading/trailing text — just one JSON object per line, separated by newlines.

Wire shape per line:

{"text": "Bullet content here.", "sources": ["https://example.com/a", "https://example.com/b"]}
{"text": "Next bullet.", "sources": ["https://example.com/c"]}

Rules:
- Exactly one JSON object per line.
- Keys are `text` (string) and `sources` (array of URL strings).
- URLs in `sources` must be pulled from the breadth/depth blocks above. Do not invent URLs.
- Do NOT emit [N] markers — the system appends them after parsing.
```

Keep the same template variables (`$name`, `$office`, `$breadth_block`, `$depth_block`) in the same positions as `formatter_user.txt`. Do not introduce new `$`-variables (the `string.Template` substitution only provides those four). If example text contains a literal `$`, escape it as `$$`.

- [ ] **Step 3: Verify the template substitutes cleanly**

Run:
```bash
cd backend && conda run -n my-reps python -c "
from string import Template
from pathlib import Path
t = Template(Path('research/overview/prompts/formatter_user_streaming.txt').read_text())
print(t.substitute(name='X', office='Y', breadth_block='B', depth_block='D')[:80])
print('ok')
"
```
Expected: prints a prompt prefix then `ok` (no `KeyError`/`ValueError` from stray `$`).

- [ ] **Step 4: Commit**

```bash
git add backend/research/overview/prompts/formatter_user_streaming.txt
git commit -m "feat(formatter): add NDJSON streaming user prompt"
```

---

## Task 9: Surface `progress` on the research API response

**Files:**
- Modify: `backend/routers/overview.py`
- Test: `backend/tests/test_overview_progress_response.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_overview_progress_response.py`:

```python
from routers.overview import ProgressInfo, _progress_for
from store.research_store import ResearchTask


def test_progress_for_in_progress_task():
    task = ResearchTask(research_id="x", status="in_progress")
    task.progress_pct = 45
    task.progress_label = "Sorting through sources"
    p = _progress_for(task)
    assert isinstance(p, ProgressInfo)
    assert p.pct == 45
    assert p.label == "Sorting through sources"


def test_progress_for_pending_task():
    task = ResearchTask(research_id="x", status="pending")
    p = _progress_for(task)
    assert p is not None
    assert p.pct == 0
    assert p.label == "Getting started"


def test_progress_for_complete_task_is_none():
    task = ResearchTask(research_id="x", status="complete")
    assert _progress_for(task) is None


def test_progress_for_failed_task_is_none():
    task = ResearchTask(research_id="x", status="failed")
    assert _progress_for(task) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && conda run -n my-reps pytest tests/test_overview_progress_response.py -v`
Expected: FAIL (`ImportError: cannot import name 'ProgressInfo'`).

- [ ] **Step 3: Add `ProgressInfo`, `_progress_for`, and wire into the response**

In `backend/routers/overview.py`:

Add `ProgressInfo` and extend `ResearchResponse` (replace the existing `ResearchResponse` class):

```python
class ProgressInfo(BaseModel):
    pct: int
    label: str


class ResearchResponse(BaseModel):
    research_id: str
    status: str  # "pending" | "in_progress" | "complete" | "failed"
    summary: ResearchSummary | None = None
    progress: ProgressInfo | None = None
```

Add the helper (place it after the `ResearchResponse` definition, before `_run_research`):

```python
def _progress_for(task) -> ProgressInfo | None:
    """Surface progress only while research is in flight."""
    if task.status in ("pending", "in_progress"):
        return ProgressInfo(pct=task.progress_pct, label=task.progress_label)
    return None
```

Replace the `get_research` return block:

```python
@router.get("/api/research/{research_id}")
async def get_research(research_id: str) -> ResearchResponse:
    task = await get_research_store().get(research_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Research task not found or expired.")
    return ResearchResponse(
        research_id=task.research_id,
        status=task.status,
        summary=task.summary,
        progress=_progress_for(task),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && conda run -n my-reps pytest tests/test_overview_progress_response.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/routers/overview.py backend/tests/test_overview_progress_response.py
git commit -m "feat(api): add progress field to research response"
```

---

## Task 10: `facts` table + seed in schema

**Files:**
- Modify: `backend/schema.sql`
- Create: `backend/migrations/2026-05-29-facts.sql`

- [ ] **Step 1: Append the table + seed to `schema.sql`**

Append to the end of `backend/schema.sql`:

```sql
-- ---------------------------------------------------------------------------
-- Civics / America fun facts shown in the loading carousel while a rep's
-- AI overview is being researched. Reference data; edit rows directly.
-- ---------------------------------------------------------------------------
CREATE TABLE facts (
    id          SERIAL PRIMARY KEY,
    text        TEXT NOT NULL,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO facts (text) VALUES
  ('The U.S. Constitution is the oldest written national constitution still in use, ratified in 1788.'),
  ('The House of Representatives has 435 voting members, a number fixed by law since 1929.'),
  ('Each U.S. state gets exactly two senators, regardless of population — so Wyoming and California have equal Senate representation.'),
  ('A senator serves a six-year term; a House representative serves a two-year term.'),
  ('It takes a two-thirds vote of both chambers of Congress to override a presidential veto.'),
  ('The Bill of Rights is the name for the first ten amendments to the Constitution, ratified in 1791.'),
  ('Washington, D.C. residents could not vote for president until the 23rd Amendment was ratified in 1961.'),
  ('The Speaker of the House is second in the line of presidential succession, after the vice president.'),
  ('Congress has the sole power to declare war, though it has formally done so only 11 times.'),
  ('The 26th Amendment lowered the voting age from 21 to 18 in 1971.'),
  ('There are 50 stars on the American flag for the states and 13 stripes for the original colonies.'),
  ('A filibuster in the Senate can be ended by a "cloture" vote, which today generally requires 60 senators.'),
  ('The first Congress in 1789 had just 26 senators and 65 representatives.'),
  ('Federal judges, including Supreme Court justices, are appointed for life and serve "during good behavior."'),
  ('Only the House can introduce bills that raise revenue, per the Constitution''s Origination Clause.'),
  ('The presidential term limit of two terms was set by the 22nd Amendment, ratified in 1951.'),
  ('Voter turnout in U.S. presidential elections is typically higher than in midterm congressional elections.'),
  ('The word "gerrymander" dates to 1812, named for Massachusetts Governor Elbridge Gerry and a salamander-shaped district.');
```

> Note the escaped single quote in `Constitution''s` (SQL string escaping).

- [ ] **Step 2: Create a standalone migration for the existing prod DB**

Create `backend/migrations/2026-05-29-facts.sql` containing the **same** `CREATE TABLE facts (...)` and `INSERT INTO facts ...` statements as Step 1 (verbatim copy). This is the one-off script to run against the already-provisioned database (since `schema.sql` is apply-once for fresh DBs).

- [ ] **Step 3: Commit**

```bash
git add backend/schema.sql backend/migrations/2026-05-29-facts.sql
git commit -m "feat(db): add facts table + seed"
```

> Applying to a live DB (dev/prod) is an operational step in the Rollout section, not part of this commit.

---

## Task 11: `get_civics_facts` DB accessor

**Files:**
- Modify: `backend/db.py`
- Test: `backend/tests/test_get_civics_facts.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_get_civics_facts.py`:

```python
import asyncio

import db


class _FakePool:
    def __init__(self, rows):
        self._rows = rows
        self.last_query = None

    async def fetch(self, query):
        self.last_query = query
        return self._rows


def test_get_civics_facts_returns_text_list(monkeypatch):
    fake = _FakePool([{"text": "Fact one"}, {"text": "Fact two"}])

    async def fake_get_pool():
        return fake

    monkeypatch.setattr(db, "get_pool", fake_get_pool)

    result = asyncio.run(db.get_civics_facts())
    assert result == ["Fact one", "Fact two"]
    assert "WHERE active" in fake.last_query
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && conda run -n my-reps pytest tests/test_get_civics_facts.py -v`
Expected: FAIL (`AttributeError: module 'db' has no attribute 'get_civics_facts'`).

- [ ] **Step 3: Add the accessor**

In `backend/db.py`, add (near `get_issues_taxonomy`):

```python
async def get_civics_facts() -> list[str]:
    """Return active civics/America facts for the loading carousel, ordered."""
    pool = await get_pool()
    rows = await pool.fetch("SELECT text FROM facts WHERE active ORDER BY id")
    return [r["text"] for r in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && conda run -n my-reps pytest tests/test_get_civics_facts.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/db.py backend/tests/test_get_civics_facts.py
git commit -m "feat(db): add get_civics_facts accessor"
```

---

## Task 12: `/api/facts` endpoint

**Files:**
- Create: `backend/routers/facts.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_facts_router.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_facts_router.py`:

```python
import asyncio

import routers.facts as facts_router


def test_get_facts_returns_facts(monkeypatch):
    async def fake_get_civics_facts():
        return ["A", "B", "C"]

    monkeypatch.setattr(facts_router, "get_civics_facts", fake_get_civics_facts)

    resp = asyncio.run(facts_router.get_facts())
    assert resp.facts == ["A", "B", "C"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && conda run -n my-reps pytest tests/test_facts_router.py -v`
Expected: FAIL (`ModuleNotFoundError: routers.facts`).

- [ ] **Step 3: Create the router**

Create `backend/routers/facts.py`:

```python
from fastapi import APIRouter
from pydantic import BaseModel

from db import get_civics_facts

router = APIRouter()


class FactsResponse(BaseModel):
    facts: list[str]


@router.get("/api/facts")
async def get_facts() -> FactsResponse:
    return FactsResponse(facts=await get_civics_facts())
```

- [ ] **Step 4: Register the router in `main.py`**

In `backend/main.py`, add the import (with the other router imports):

```python
from routers.facts import router as facts_router
```

and register it (after `app.include_router(issues_router)`):

```python
app.include_router(facts_router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && conda run -n my-reps pytest tests/test_facts_router.py -v`
Expected: PASS (1 passed).

- [ ] **Step 6: Run the full backend suite**

Run: `cd backend && conda run -n my-reps pytest tests/ -v`
Expected: PASS (all tests green).

- [ ] **Step 7: Commit**

```bash
git add backend/routers/facts.py backend/main.py backend/tests/test_facts_router.py
git commit -m "feat(api): add GET /api/facts endpoint"
```

---

## Task 13: Frontend types — `ProgressInfo` + `ResearchResponse.progress`

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add the `ProgressInfo` interface and the response field**

In `frontend/src/types/index.ts`, replace the `ResearchResponse` interface:

```ts
export interface ResearchResponse {
  research_id: string;
  status: "pending" | "in_progress" | "complete" | "failed";
  summary: ResearchSummary | null;
}
```

with:

```ts
export interface ProgressInfo {
  pct: number;
  label: string;
}

export interface ResearchResponse {
  research_id: string;
  status: "pending" | "in_progress" | "complete" | "failed";
  summary: ResearchSummary | null;
  progress?: ProgressInfo | null;
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(types): add ProgressInfo and progress on ResearchResponse"
```

---

## Task 14: `useResearchQuery` — track + expose progress

**Files:**
- Modify: `frontend/src/hooks/useResearchQuery.ts`

- [ ] **Step 1: Import `ProgressInfo` and extend `ResearchEntry`**

In `frontend/src/hooks/useResearchQuery.ts`, update the type import:

```ts
import type { Representative, ResearchSummary, ResearchResponse } from "@/types";
```

to:

```ts
import type { Representative, ResearchSummary, ResearchResponse, ProgressInfo } from "@/types";
```

Replace the `ResearchEntry` interface:

```ts
interface ResearchEntry {
  status: ResearchStatus;
  summary: ResearchSummary | null;
  researchId: string | null;
}
```

with:

```ts
interface ResearchEntry {
  status: ResearchStatus;
  summary: ResearchSummary | null;
  researchId: string | null;
  progress: ProgressInfo | null;
}
```

- [ ] **Step 2: Update the `getEntry` default**

Replace:

```ts
      return queryClient.getQueryData<ResearchEntry>(["research", key]) ?? {
        status: "idle",
        summary: null,
        researchId: null,
      };
```

with:

```ts
      return queryClient.getQueryData<ResearchEntry>(["research", key]) ?? {
        status: "idle",
        summary: null,
        researchId: null,
        progress: null,
      };
```

- [ ] **Step 3: Update the poll loop to persist progress**

In `startPolling`, replace the `complete` and `in_progress`/`pending` branches:

```ts
          const data: ResearchResponse = await resp.json();
          if (data.status === "complete") {
            stopPolling(key);
            setEntry(key, { status: "complete", summary: data.summary, researchId });
            bumpVersion();
          } else if (data.status === "in_progress" || data.status === "pending") {
            if (data.summary) {
              setEntry(key, { status: "loading", summary: data.summary, researchId });
              bumpVersion();
            }
          } else if (data.status === "failed") {
            stopPolling(key);
            setEntry(key, { status: "failed", summary: null, researchId });
            bumpVersion();
          }
```

with:

```ts
          const data: ResearchResponse = await resp.json();
          if (data.status === "complete") {
            stopPolling(key);
            setEntry(key, {
              status: "complete",
              summary: data.summary,
              researchId,
              progress: null,
            });
            bumpVersion();
          } else if (data.status === "in_progress" || data.status === "pending") {
            const prev = getEntry(key);
            setEntry(key, {
              status: "loading",
              summary: data.summary ?? prev.summary,
              researchId,
              progress: data.progress ?? prev.progress,
            });
            bumpVersion();
          } else if (data.status === "failed") {
            stopPolling(key);
            setEntry(key, {
              status: "failed",
              summary: null,
              researchId,
              progress: null,
            });
            bumpVersion();
          }
```

Then add `getEntry` to `startPolling`'s dependency array:

```ts
    [stopPolling, setEntry, bumpVersion, getEntry]
```

- [ ] **Step 4: Update the `requestResearch` setEntry calls**

In `requestResearch`, every `setEntry` call must include `progress`. Replace the four calls in that function as follows:

Initial loading set:
```ts
      setEntry(key, { status: "loading", summary: null, researchId: null, progress: null });
```
Failure (non-ok response):
```ts
            setEntry(key, { status: "failed", summary: null, researchId: null, progress: null });
```
Immediate-complete (cached) branch:
```ts
            setEntry(key, { status: "complete", summary: data.summary, researchId: data.research_id, progress: null });
```
Persist-researchId loading branch:
```ts
          setEntry(key, { status: "loading", summary: data.summary ?? null, researchId: data.research_id, progress: data.progress ?? null });
```
Catch-block failure:
```ts
          setEntry(key, { status: "failed", summary: null, researchId: null, progress: null });
```

- [ ] **Step 5: Add the `getProgress` accessor and export it**

After the `getSummary` definition, add:

```ts
  const getProgress = useCallback(
    (rep: Representative): ProgressInfo | null => {
      void cacheVersion.data;
      return getEntry(repKey(rep)).progress;
    },
    [getEntry, cacheVersion.data]
  );
```

And update the return statement:

```ts
  return { requestResearch, getStatus, getSummary, getProgress };
```

- [ ] **Step 6: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/hooks/useResearchQuery.ts
git commit -m "feat(hooks): track and expose research progress"
```

---

## Task 15: `useFactsQuery` hook

**Files:**
- Create: `frontend/src/hooks/useFactsQuery.ts`

- [ ] **Step 1: Create the hook**

Create `frontend/src/hooks/useFactsQuery.ts`:

```ts
import { useQuery } from "@tanstack/react-query";

const API_URL = import.meta.env.VITE_API_URL;

/**
 * Fetches the civics/America fun facts shown in the loading carousel.
 * Cached for the whole session (facts don't change while the app is open).
 */
export function useFactsQuery() {
  return useQuery({
    queryKey: ["facts"],
    queryFn: async (): Promise<string[]> => {
      const resp = await fetch(`${API_URL}/api/facts`);
      if (!resp.ok) return [];
      const data = await resp.json();
      return (data.facts as string[]) ?? [];
    },
    staleTime: Infinity,
  });
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useFactsQuery.ts
git commit -m "feat(hooks): add useFactsQuery"
```

---

## Task 16: `ResearchProgress` component

**Files:**
- Create: `frontend/src/components/overview/ResearchProgress.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/overview/ResearchProgress.tsx`:

```tsx
import type { ProgressInfo } from "@/types";

/**
 * Filling progress bar shown while a rep overview is being researched.
 * Driven by per-node progress from the backend; falls back to 0% /
 * "Getting started" on the first poll before any node has reported.
 */
export function ResearchProgress({ progress }: { progress?: ProgressInfo | null }) {
  const pct = progress?.pct ?? 0;
  const label = progress?.label ?? "Getting started";
  const clamped = Math.min(100, Math.max(0, pct));

  return (
    <div className="space-y-1.5 mt-1">
      <div className="flex items-center justify-between text-xs font-medium text-muted-foreground">
        <span className="italic">{label}…</span>
        <span>{clamped}%</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-foreground transition-all duration-700 ease-out"
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/overview/ResearchProgress.tsx
git commit -m "feat(overview): add ResearchProgress component"
```

---

## Task 17: `FactsCarousel` component

**Files:**
- Create: `frontend/src/components/overview/FactsCarousel.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/overview/FactsCarousel.tsx`:

```tsx
import { useEffect, useState } from "react";
import { useFactsQuery } from "@/hooks/useFactsQuery";

const ROTATE_MS = 6000;

/**
 * Rotating civics/America fun facts shown while research loads. Renders
 * nothing until facts have loaded, so the progress bar alone carries the
 * loading state if the facts endpoint is empty or slow.
 */
export function FactsCarousel() {
  const { data: facts } = useFactsQuery();
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    if (!facts || facts.length === 0) return;
    setIdx(Math.floor(Math.random() * facts.length));
    const timer = setInterval(() => {
      setIdx((i) => (i + 1) % facts.length);
    }, ROTATE_MS);
    return () => clearInterval(timer);
  }, [facts]);

  if (!facts || facts.length === 0) return null;

  return (
    <div className="mt-3 rounded-lg border bg-muted/40 p-3">
      <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
        Did you know?
      </p>
      <p key={idx} className="mt-1 text-sm leading-relaxed">
        {facts[idx]}
      </p>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/overview/FactsCarousel.tsx
git commit -m "feat(overview): add FactsCarousel component"
```

---

## Task 18: Bullets `ResearchContent` — progress/facts gate + trailer skeleton

**Files:**
- Modify: `frontend/src/components/overview/bullets/ResearchContent.tsx`

- [ ] **Step 1: Rewrite the component with the new gate**

Replace the full contents of `frontend/src/components/overview/bullets/ResearchContent.tsx` with:

```tsx
/**
 * Bullets research content renderer — single blended bullet list with
 * inline citation markers resolved against a unified citation pool.
 *
 * While loading with no bullets yet, shows a per-node progress bar plus a
 * rotating fun-facts carousel. Once bullets start streaming in, renders them
 * with a small trailer skeleton until the task completes.
 */

import type { BulletsResearchSummary } from "./types";
import type { ProgressInfo } from "@/types";
import { FurtherReading } from "@/components/FurtherReading";
import { renderInline } from "@/components/overview/renderInline";
import { ResearchProgress } from "@/components/overview/ResearchProgress";
import { FactsCarousel } from "@/components/overview/FactsCarousel";
import { Skeleton } from "@/components/ui/skeleton";

function BulletsTrailerSkeleton() {
  return (
    <div className="space-y-1 pt-1" aria-hidden>
      <Skeleton className="h-3.5 w-5/6" />
      <Skeleton className="h-3.5 w-2/3" />
    </div>
  );
}

export function ResearchContent({
  summary,
  status,
  progress,
}: {
  summary: BulletsResearchSummary;
  status?: "loading" | "complete" | "failed";
  progress?: ProgressInfo | null;
}) {
  const { bullets, citations, sources } = summary;

  // Nothing written yet: show the progress bar + facts carousel.
  if (bullets.length === 0) {
    return (
      <div className="space-y-2 text-sm leading-relaxed">
        <ResearchProgress progress={progress} />
        <FactsCarousel />
      </div>
    );
  }

  return (
    <div className="space-y-3 text-sm leading-relaxed prose prose-sm prose-neutral dark:prose-invert max-w-none mt-2">
      <ul className="list-disc pl-5 space-y-1.5 marker:text-muted-foreground">
        {bullets.map((b, i) => (
          <li key={i}>{renderInline(b, citations)}</li>
        ))}
      </ul>
      {status === "loading" && <BulletsTrailerSkeleton />}
      <FurtherReading sources={sources} />
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: errors at the `overview/index.tsx` wrapper call site (it doesn't pass `status`/`progress` yet) — that's fixed in Task 19. The `bullets/ResearchContent.tsx` file itself should have no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/overview/bullets/ResearchContent.tsx
git commit -m "feat(overview): progress + facts loading gate with trailer skeleton"
```

---

## Task 19: Thread `status`/`progress` through the overview dispatch wrapper

**Files:**
- Modify: `frontend/src/components/overview/index.tsx`

- [ ] **Step 1: Update the wrapper to accept and forward the new props**

Replace the full contents of `frontend/src/components/overview/index.tsx` with:

```tsx
/**
 * Overview dispatch: the backend may return a v1 sectioned summary OR a
 * BulletsResearchSummary (default pipeline, legacy v2/v3). Consumers get a
 * single ResearchContent component and a union type; the component picks a
 * renderer at runtime based on the response shape.
 */

import type { ResearchSummary as V1ResearchSummary } from "./v1";
import type { BulletsResearchSummary } from "./bullets";
import type { ProgressInfo } from "@/types";
import { ResearchContent as V1ResearchContent } from "./v1";
import { ResearchContent as BulletsResearchContent } from "./bullets";

export type ResearchSummary = V1ResearchSummary | BulletsResearchSummary;

export function isBullets(summary: ResearchSummary): summary is BulletsResearchSummary {
  return "bullets" in summary;
}

export function ResearchContent({
  summary,
  status,
  progress,
}: {
  summary: ResearchSummary;
  status?: "loading" | "complete" | "failed";
  progress?: ProgressInfo | null;
}) {
  if (isBullets(summary)) {
    return <BulletsResearchContent summary={summary} status={status} progress={progress} />;
  }
  return <V1ResearchContent summary={summary} />;
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors (the v1 path ignores the new optional props; the bullets path now receives them).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/overview/index.tsx
git commit -m "feat(overview): forward status/progress through dispatch wrapper"
```

---

## Task 20: `RepCard` — progress prop, collapse loading branches, drop "Scraping" copy

**Files:**
- Modify: `frontend/src/components/RepCard.tsx`
- Modify: `frontend/src/pages/RepresentativesPage.tsx`

- [ ] **Step 1: Add the `progress` prop to `RepCard`**

In `frontend/src/components/RepCard.tsx`, update the imports — add `ProgressInfo`:

Find the existing types import (it imports `Representative`, etc. from `@/types`) and ensure `ProgressInfo` is included, e.g.:

```ts
import type { Representative, ProgressInfo } from "@/types";
```

(Add `ProgressInfo` to the existing `@/types` import rather than creating a duplicate import line.)

Replace the props interface:

```ts
interface RepCardProps {
  rep: Representative;
  researchStatus: ResearchStatus;
  summary: ResearchSummary | null;
  onResearch: () => void;
}

export function RepCard({ rep, researchStatus, summary, onResearch }: RepCardProps) {
```

with:

```ts
interface RepCardProps {
  rep: Representative;
  researchStatus: ResearchStatus;
  summary: ResearchSummary | null;
  progress?: ProgressInfo | null;
  onResearch: () => void;
}

export function RepCard({ rep, researchStatus, summary, progress, onResearch }: RepCardProps) {
```

- [ ] **Step 2: Replace the two loading branches with one**

In `frontend/src/components/RepCard.tsx`, replace this block:

```tsx
        {researchStatus === "loading" && !summary && (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground italic">
              Scraping the web for information about your representative -- this usually takes 30-60 seconds...
            </p>
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        )}

        {(researchStatus === "loading" && summary) && (
          <Collapsible defaultOpen>
            <CollapsibleTrigger className="flex w-full items-center gap-1 text-xs font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground cursor-pointer group">
              <ChevronRight className="h-4 w-4 group-data-[state=open]:hidden" />
              <ChevronDown className="h-4 w-4 group-data-[state=closed]:hidden" />
              AI Overview
              <span className="ml-2 text-[11px] font-medium normal-case tracking-normal text-muted-foreground italic">(scraping the web — usually 30-60 seconds…)</span>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <ResearchContent summary={summary} />
            </CollapsibleContent>
          </Collapsible>
        )}
```

with:

```tsx
        {researchStatus === "loading" && (
          <Collapsible defaultOpen>
            <CollapsibleTrigger className="flex w-full items-center gap-1 text-xs font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground cursor-pointer group">
              <ChevronRight className="h-4 w-4 group-data-[state=open]:hidden" />
              <ChevronDown className="h-4 w-4 group-data-[state=closed]:hidden" />
              AI Overview
            </CollapsibleTrigger>
            <CollapsibleContent>
              <ResearchContent
                summary={summary ?? { bullets: [], citations: [] }}
                status="loading"
                progress={progress}
              />
            </CollapsibleContent>
          </Collapsible>
        )}
```

- [ ] **Step 3: Pass `status="complete"` on the complete branch**

In `frontend/src/components/RepCard.tsx`, in the `researchStatus === "complete"` branch, find:

```tsx
              <CollapsibleContent>
                <ResearchContent summary={summary} />
              </CollapsibleContent>
```

and replace with:

```tsx
              <CollapsibleContent>
                <ResearchContent summary={summary} status="complete" />
              </CollapsibleContent>
```

- [ ] **Step 4: Remove the now-unused `Skeleton` import if it's unused**

Run: `cd frontend && grep -n "Skeleton" src/components/RepCard.tsx`
If the only remaining match is the import line, remove the import:

```ts
import { Skeleton } from "@/components/ui/skeleton";
```

(If `Skeleton` is still used elsewhere in the file, leave the import.)

- [ ] **Step 5: Pass `progress` from `RepresentativesPage`**

In `frontend/src/pages/RepresentativesPage.tsx`, update the hook destructure:

```ts
  const { requestResearch, getStatus, getSummary } = useResearch();
```

to:

```ts
  const { requestResearch, getStatus, getSummary, getProgress } = useResearch();
```

And update the `<RepCard>` usage:

```tsx
                        <RepCard
                          key={`${rep.name}-${rep.office}`}
                          rep={rep}
                          researchStatus={getStatus(rep)}
                          summary={getSummary(rep)}
                          onResearch={() => requestResearch(rep)}
                        />
```

to:

```tsx
                        <RepCard
                          key={`${rep.name}-${rep.office}`}
                          rep={rep}
                          researchStatus={getStatus(rep)}
                          summary={getSummary(rep)}
                          progress={getProgress(rep)}
                          onResearch={() => requestResearch(rep)}
                        />
```

- [ ] **Step 6: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/RepCard.tsx frontend/src/pages/RepresentativesPage.tsx
git commit -m "feat(reps): progress+facts loading state in RepCard"
```

---

## Task 21: `CandidateCard` — same treatment, threaded through `ElectionCard`

**Files:**
- Modify: `frontend/src/components/CandidateCard.tsx`
- Modify: `frontend/src/components/ElectionCard.tsx`
- Modify: `frontend/src/pages/ElectionsPage.tsx`

- [ ] **Step 1: Add the `progress` prop to `CandidateCard`**

In `frontend/src/components/CandidateCard.tsx`, add `ProgressInfo` to the `@/types` import, then replace the props interface + signature:

```ts
interface CandidateCardProps {
  candidate: Candidate;
  rep: Representative;
  researchStatus: ResearchStatus;
  summary: ResearchSummary | null;
  onResearch: () => void;
}

export function CandidateCard({
  candidate,
  rep,
  researchStatus,
  summary,
  onResearch,
}: CandidateCardProps) {
```

with:

```ts
interface CandidateCardProps {
  candidate: Candidate;
  rep: Representative;
  researchStatus: ResearchStatus;
  summary: ResearchSummary | null;
  progress?: ProgressInfo | null;
  onResearch: () => void;
}

export function CandidateCard({
  candidate,
  rep,
  researchStatus,
  summary,
  progress,
  onResearch,
}: CandidateCardProps) {
```

- [ ] **Step 2: Collapse the loading branches**

In `frontend/src/components/CandidateCard.tsx`, replace:

```tsx
        {researchStatus === "loading" && !summary && (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground italic">
              Scraping the web for information about this candidate -- this usually takes 30-60 seconds...
            </p>
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        )}

        {researchStatus === "loading" && summary && (
          <Collapsible defaultOpen>
            <CollapsibleTrigger className="flex w-full items-center gap-1 text-xs font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground cursor-pointer group">
              <ChevronRight className="h-4 w-4 group-data-[state=open]:hidden" />
              <ChevronDown className="h-4 w-4 group-data-[state=closed]:hidden" />
              AI Overview
              <span className="ml-2 text-[11px] font-medium normal-case tracking-normal text-muted-foreground italic">(scraping the web — usually 30-60 seconds…)</span>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <ResearchContent summary={summary} />
            </CollapsibleContent>
          </Collapsible>
        )}
```

with:

```tsx
        {researchStatus === "loading" && (
          <Collapsible defaultOpen>
            <CollapsibleTrigger className="flex w-full items-center gap-1 text-xs font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground cursor-pointer group">
              <ChevronRight className="h-4 w-4 group-data-[state=open]:hidden" />
              <ChevronDown className="h-4 w-4 group-data-[state=closed]:hidden" />
              AI Overview
            </CollapsibleTrigger>
            <CollapsibleContent>
              <ResearchContent
                summary={summary ?? { bullets: [], citations: [] }}
                status="loading"
                progress={progress}
              />
            </CollapsibleContent>
          </Collapsible>
        )}
```

- [ ] **Step 3: Pass `status="complete"` on the complete branch**

In `frontend/src/components/CandidateCard.tsx`, in the `researchStatus === "complete"` branch, replace:

```tsx
            <CollapsibleContent>
              <ResearchContent summary={summary} />
            </CollapsibleContent>
```

with:

```tsx
            <CollapsibleContent>
              <ResearchContent summary={summary} status="complete" />
            </CollapsibleContent>
```

- [ ] **Step 4: Remove the now-unused `Skeleton` import if unused**

Run: `cd frontend && grep -n "Skeleton" src/components/CandidateCard.tsx`
If the only remaining match is the import, remove `import { Skeleton } from "@/components/ui/skeleton";`.

- [ ] **Step 5: Thread a progress getter through `ElectionCard`**

In `frontend/src/components/ElectionCard.tsx`, add `ProgressInfo` to the `@/types` import. Add to the props interface (next to `getCandidateResearchSummary`):

```ts
  getCandidateResearchProgress: (candidate: Candidate) => ProgressInfo | null;
```

Add it to the destructured props (next to `getCandidateResearchSummary`):

```ts
  getCandidateResearchProgress,
```

In the `<CandidateCard>` usage, add the prop (next to `summary=...`):

```tsx
                        progress={getCandidateResearchProgress(candidate)}
```

- [ ] **Step 6: Pass it from `ElectionsPage`**

In `frontend/src/pages/ElectionsPage.tsx`, update the hook destructure:

```ts
  const { requestResearch, getStatus, getSummary } = useResearch();
```

to:

```ts
  const { requestResearch, getStatus, getSummary, getProgress } = useResearch();
```

Then add to the `<ElectionCard>` usage (next to `getCandidateResearchSummary={...}`):

```tsx
              getCandidateResearchProgress={(c) => getProgress(candidateToRep(c))}
```

- [ ] **Step 7: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/CandidateCard.tsx frontend/src/components/ElectionCard.tsx frontend/src/pages/ElectionsPage.tsx
git commit -m "feat(elections): progress+facts loading state in CandidateCard"
```

---

## Task 22: Frontend build/lint + manual smoke

**Files:** none (verification only)

- [ ] **Step 1: Lint + production build**

Run: `cd frontend && npm run lint && npm run build`
Expected: lint passes, build succeeds (tsc + Vite).

- [ ] **Step 2: Apply the facts migration to the dev DB**

With the Cloud SQL Auth Proxy running (see README), run the migration against the dev database, e.g.:

```bash
psql "$DATABASE_URL" -f backend/migrations/2026-05-29-facts.sql
```
Expected: `CREATE TABLE` + `INSERT 0 18`. Verify: `psql "$DATABASE_URL" -c "SELECT count(*) FROM facts;"` returns 18.

- [ ] **Step 3: Run both servers**

Backend: `cd backend && conda run -n my-reps uvicorn main:app --reload`
Frontend: `cd frontend && npm run dev`

Confirm `GET /api/facts` returns the seeded facts: `curl -s http://localhost:8000/api/facts | head -c 200`.

- [ ] **Step 4: Manual smoke in the browser**

With `OVERVIEW_V4_FORMATTER_STREAMING` unset (defaults on) and `DISABLE_REP_CACHE=true` (so the pipeline actually runs), enter an address, open `/reps`, and click "Generate AI Overview" on a rep. Verify:
- Progress bar fills across nodes with advancing labels ("Planning what to research" → "Searching the web" → … → "Writing the summary").
- The "Did you know?" facts carousel rotates while loading.
- The first streamed bullet retires the progress bar; bullets accumulate with a small trailer skeleton beneath them.
- On completion the trailer skeleton disappears; citations + Further Reading (if `OVERVIEW_V4_SHOW_SOURCES=true`) render.
- Failure path: set `OVERVIEW_V4_FORMATTER_MIN_BULLETS=99`, re-run — the card shows "Research unavailable" + Retry, not a stuck bar.
- Fallback path: set `OVERVIEW_V4_FORMATTER_STREAMING=false`, re-run — bullets appear all at once on completion (no streaming), no errors.

- [ ] **Step 5: Commit (if any lint autofixes were applied)**

```bash
git add -A
git commit -m "chore(frontend): lint/build fixes for progress+facts" || echo "nothing to commit"
```

---

## Task 23: Documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/initiatives/V4_PERFORMANCE.md`

- [ ] **Step 1: Add env vars + facts to `CLAUDE.md`**

In `CLAUDE.md`, in the Environment Variables section, add entries:

```
- `OVERVIEW_V4_FORMATTER_STREAMING` — v4 only: when `true` (default), the formatter streams bullets as NDJSON (one `{"text","sources"}` object per line) and writes each parsed bullet to the research store via `update_partial`, so the frontend renders bullets as they land. When `false`, falls back to the blocking `with_structured_output` path. The structured path remains the escape hatch.
- `OVERVIEW_V4_FORMATTER_MIN_BULLETS` — v4 only: minimum valid bullets the streaming formatter must produce; below this the run fails (→ task `failed` → frontend retry UI) rather than showing a too-thin overview (default `3`).
```

In the relevant architecture prose, note: the v4 nodes report per-node progress to `InMemoryResearchStore.update_progress` (mapping in `research/overview/progress.py`), surfaced on `ResearchResponse.progress` and polled by the frontend to drive the loading progress bar; the `facts` table + `GET /api/facts` (`routers/facts.py`, `db.get_civics_facts`) serve the loading-screen fun-facts carousel.

- [ ] **Step 2: Mark the formatter-streaming item in `V4_PERFORMANCE.md`**

In `docs/initiatives/V4_PERFORMANCE.md`, find the formatter streaming `[L]` open idea and mark it shipped (`[x]`), with a one-paragraph note: NDJSON line streaming replaced the blocking structured-output call (default on), per-node progress bar + DB-served facts carousel added for the loading phase; first bullet now lands well before the full block. Calibrate `PROGRESS_STEPS` percentages against observed node timings.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md docs/initiatives/V4_PERFORMANCE.md
git commit -m "docs: document streaming, progress, and facts features"
```

---

## Self-Review Notes

- **Spec coverage:** progress store/registry/reporting (Tasks 2–5, 9), formatter streaming (Tasks 6–8), facts DB/endpoint/hook/carousel (Tasks 10–12, 15, 17), progress component (16), frontend gate + plumbing (13–14, 18–21), tests + manual smoke (22), docs (23). All spec sections map to a task.
- **Type consistency:** `ProgressInfo {pct, label}` is identical in backend (`routers/overview.py`) and frontend (`types/index.ts`); `getProgress` matches its consumers; `_handle_line`/`_consume_stream` signatures match their tests; `ResearchContent` accepts `status` + `progress` uniformly across wrapper, bullets renderer, and both cards.
- **No placeholders:** every code step shows complete content; the only intentional authoring step is the fact strings, which are provided verbatim in Task 10.
