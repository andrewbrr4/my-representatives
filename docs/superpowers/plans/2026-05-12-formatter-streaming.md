# Formatter Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stream the v4 formatter's bullet output to the frontend as each bullet is produced, so the user sees the first bullet in ~5–8s instead of waiting ~22s for the full block.

**Architecture:** Replace the formatter's `with_structured_output` call with NDJSON line streaming (`{"text":"...","sources":["url",...]}` per line). Backend parses each completed line, builds `[N]` markers + citations incrementally, and writes the growing `ResearchSummary` to `InMemoryResearchStore` via a new `update_partial()` method on every new bullet. Existing 2s frontend poll picks up partials. Gated behind `OVERVIEW_V4_FORMATTER_STREAMING` env var (default off); structured-output path stays as fallback.

**Tech Stack:** FastAPI + LangChain `ChatAnthropic.astream` (backend), React + TanStack Query (frontend), pytest + pytest-asyncio (new test infra).

**Spec:** `docs/superpowers/specs/2026-05-12-formatter-streaming-design.md` — read first if unfamiliar.

---

## Task 1: Set up pytest test infrastructure

The backend has no existing test suite. Add minimal pytest config so subsequent tasks can write tests.

**Files:**
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/pytest.ini`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add pytest deps to requirements.txt**

Append two lines to `backend/requirements.txt`:

```
pytest>=8.3.0
pytest-asyncio>=0.24.0
```

- [ ] **Step 2: Install in conda env**

Run:

```bash
conda activate my-reps && pip install -r backend/requirements.txt
```

Expected: pytest and pytest-asyncio install successfully.

- [ ] **Step 3: Create empty package marker**

Create `backend/tests/__init__.py` with empty content (just an empty file).

- [ ] **Step 4: Create conftest.py setting required env vars**

Create `backend/tests/conftest.py`:

```python
"""Test-suite-wide fixtures and env setup.

Backend modules import-time-read CLAUDE_MODEL / RESEARCH_MAX_TOKENS, so
we set them here before any test module imports backend code.
"""

import os

os.environ.setdefault("CLAUDE_MODEL", "claude-sonnet-4-20250514")
os.environ.setdefault("RESEARCH_MAX_TOKENS", "4096")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-used")
os.environ.setdefault("TAVILY_API_KEY", "test-key-not-used")
```

- [ ] **Step 5: Create pytest.ini**

Create `backend/pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
pythonpath = .
```

- [ ] **Step 6: Run pytest to confirm zero tests pass**

Run:

```bash
cd backend && pytest -v
```

Expected: `no tests ran in <time>` — confirms pytest is wired up. Exit code 5 (no tests) is OK.

- [ ] **Step 7: Commit**

```bash
git add backend/tests/__init__.py backend/tests/conftest.py backend/pytest.ini backend/requirements.txt
git commit -m "chore(backend): add pytest + pytest-asyncio test infrastructure"
```

---

## Task 2: Add `InMemoryResearchStore.update_partial()` method

New store method for whole-summary partial replaces. Distinct from `complete_section` (which is for v1's per-section streaming).

**Files:**
- Modify: `backend/store/research_store.py`
- Test: `backend/tests/test_research_store_update_partial.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_research_store_update_partial.py`:

```python
"""Tests for InMemoryResearchStore.update_partial — used by the v4
formatter streaming path to push partial summaries to the store as
each bullet lands."""

import pytest
from pydantic import BaseModel

from store.research_store import InMemoryResearchStore


class _FakeSummary(BaseModel):
    bullets: list[str] = []


@pytest.mark.asyncio
async def test_update_partial_replaces_summary_and_transitions_pending_to_in_progress():
    store = InMemoryResearchStore()
    await store.create("rid", total_sections=1, summary=_FakeSummary(bullets=[]))

    await store.update_partial("rid", _FakeSummary(bullets=["one"]))

    task = await store.get("rid")
    assert task.status == "in_progress"
    assert task.summary.bullets == ["one"]


@pytest.mark.asyncio
async def test_update_partial_does_not_mark_complete():
    store = InMemoryResearchStore()
    await store.create("rid", total_sections=1, summary=_FakeSummary(bullets=[]))

    await store.update_partial("rid", _FakeSummary(bullets=["a", "b", "c"]))

    task = await store.get("rid")
    assert task.status == "in_progress"  # NOT complete
    assert task.completed_sections == 0  # never bumped


@pytest.mark.asyncio
async def test_update_partial_subsequent_calls_replace_not_append():
    store = InMemoryResearchStore()
    await store.create("rid", total_sections=1, summary=_FakeSummary(bullets=[]))

    await store.update_partial("rid", _FakeSummary(bullets=["one"]))
    await store.update_partial("rid", _FakeSummary(bullets=["one", "two"]))
    await store.update_partial("rid", _FakeSummary(bullets=["one", "two", "three"]))

    task = await store.get("rid")
    assert task.summary.bullets == ["one", "two", "three"]


@pytest.mark.asyncio
async def test_update_partial_unknown_id_is_silent_noop():
    store = InMemoryResearchStore()
    # No create() call.
    await store.update_partial("missing", _FakeSummary(bullets=["x"]))
    # Should not raise.
    assert await store.get("missing") is None


@pytest.mark.asyncio
async def test_update_partial_does_not_revert_complete_status():
    """Edge: if a race occurs and complete() ran before a stray
    update_partial, status should not regress to in_progress."""
    store = InMemoryResearchStore()
    await store.create("rid", total_sections=1, summary=_FakeSummary(bullets=[]))
    await store.complete("rid", _FakeSummary(bullets=["final"]))

    await store.update_partial("rid", _FakeSummary(bullets=["partial"]))

    task = await store.get("rid")
    # Status stays complete; summary is allowed to change (last write wins
    # is acceptable here — the streaming path will not call update_partial
    # after complete in normal flow).
    assert task.status == "complete"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && pytest tests/test_research_store_update_partial.py -v
```

Expected: FAIL with `AttributeError: 'InMemoryResearchStore' object has no attribute 'update_partial'`.

- [ ] **Step 3: Add `update_partial` to `InMemoryResearchStore`**

In `backend/store/research_store.py`, add a new method after `complete()` (around line 83):

```python
    async def update_partial(self, research_id: str, summary: PydanticBaseModel) -> None:
        """Replace the in-progress summary with a newer partial.

        Sets status to in_progress if pending. Does NOT mark complete or
        bump completed_sections — the streaming caller invokes complete()
        at the end (or fail() on error). Does not regress status if the
        task is already complete or failed.
        """
        async with self._lock:
            task = self._tasks.get(research_id)
            if not task:
                return
            task.summary = summary
            if task.status == "pending":
                task.status = "in_progress"
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd backend && pytest tests/test_research_store_update_partial.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/store/research_store.py backend/tests/test_research_store_update_partial.py
git commit -m "feat(store): add InMemoryResearchStore.update_partial for streaming partials"
```

---

## Task 3: Plumb `store` and `research_id` through `V4State` and pipeline

The streaming formatter needs the store and research_id from inside the LangGraph node. Add them as optional fields on `V4State` and populate them in `pipeline.research_representative`.

**Files:**
- Modify: `backend/research/overview/state.py`
- Modify: `backend/research/overview/pipeline.py`
- Test: `backend/tests/test_pipeline_state_plumbing.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_pipeline_state_plumbing.py`:

```python
"""Verify pipeline.research_representative populates store + research_id
on V4State so the streaming formatter can use them."""

from unittest.mock import AsyncMock, patch

import pytest

from models import Representative
from store.research_store import InMemoryResearchStore


@pytest.mark.asyncio
async def test_initial_state_includes_store_and_research_id_when_provided():
    """When called with store + research_id, the pipeline must inject
    them into the initial state passed to ainvoke."""
    from research.overview import pipeline as pipeline_mod

    store = InMemoryResearchStore()
    rep = Representative(name="Test Person", office="Senator", contact={})

    captured_initial: dict = {}

    async def fake_ainvoke(initial, config=None):
        captured_initial.update(initial)
        return {"summary": None, "usage_log": []}

    with patch.object(pipeline_mod.pipeline_graph, "ainvoke", side_effect=fake_ainvoke):
        await pipeline_mod.research_representative(rep, store=store, research_id="rid-123")

    assert captured_initial.get("store") is store
    assert captured_initial.get("research_id") == "rid-123"


@pytest.mark.asyncio
async def test_initial_state_omits_store_when_not_provided():
    """When called without store, initial state must not have store/research_id
    keys (TypedDict total=False so absence is fine)."""
    from research.overview import pipeline as pipeline_mod

    rep = Representative(name="Test Person", office="Senator", contact={})

    captured_initial: dict = {}

    async def fake_ainvoke(initial, config=None):
        captured_initial.update(initial)
        return {"summary": None, "usage_log": []}

    with patch.object(pipeline_mod.pipeline_graph, "ainvoke", side_effect=fake_ainvoke):
        await pipeline_mod.research_representative(rep)

    assert "store" not in captured_initial
    assert "research_id" not in captured_initial
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && pytest tests/test_pipeline_state_plumbing.py -v
```

Expected: FAIL — both assertions about `store` / `research_id` will fail because they're not currently passed in.

- [ ] **Step 3: Add fields to V4State**

In `backend/research/overview/state.py`, modify the imports and `V4State`:

Replace lines 14-15:

```python
import operator
from typing import Annotated, TypedDict
```

with:

```python
import operator
from typing import Annotated, TypedDict, TYPE_CHECKING
```

Add at the bottom of the imports block (after the existing imports, before line 22's blank line):

```python
if TYPE_CHECKING:
    from store.research_store import InMemoryResearchStore
```

Then in the `V4State` class body (after `usage_log` line 35), add:

```python
    # Streaming-formatter plumbing. Populated by pipeline.research_representative
    # only when streaming runs need to push partials. Other nodes ignore.
    store: "InMemoryResearchStore"
    research_id: str
```

(Both are optional in practice because `total=False` on the TypedDict.)

- [ ] **Step 4: Inject store and research_id in pipeline.py**

In `backend/research/overview/pipeline.py`, modify `research_representative` (around line 64). Replace:

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

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
cd backend && pytest tests/test_pipeline_state_plumbing.py -v
```

Expected: both tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/research/overview/state.py backend/research/overview/pipeline.py backend/tests/test_pipeline_state_plumbing.py
git commit -m "feat(v4): plumb store + research_id through V4State and pipeline"
```

---

## Task 4: Create NDJSON-shape user prompt for streaming formatter

A separate user-prompt file for the streaming branch. The system prompt is unchanged.

**Files:**
- Create: `backend/research/overview/prompts/formatter_user_streaming.txt`

- [ ] **Step 1: Create the prompt file**

Create `backend/research/overview/prompts/formatter_user_streaming.txt`:

```
Official: $name
Office: $office

## Breadth search results

$breadth_block

---

## Depth-research results (focused on volatile subtopics — prefer these on overlap)

$depth_block

---

Write **6–8 tight bullets** per the system instructions — the product is for a busy voter, so each bullet is ~14–22 words. Quality over quantity: a 6-bullet overview beats a padded 8-bullet one.

**OUTPUT FORMAT (CRITICAL — read carefully):**

Emit one bullet per line as a single JSON object on each line. **No outer array. No markdown fence. No commentary. No leading or trailing prose.** Just one JSON object per line, separated by `\n`.

Wire shape per line (literal example — do not include this example in your output):

```
{"text": "**Headline 1** - Sentence about the bullet.", "sources": ["https://example.com/a", "https://example.com/b"]}
{"text": "**Headline 2** - Another sentence.", "sources": ["https://example.com/c"]}
```

Rules:
- Exactly one JSON object per line. Each line must be a complete, parseable JSON object on its own.
- Keys are `text` (string) and `sources` (array of URL strings).
- URLs in `sources` must be **copied verbatim from the breadth or depth blocks above**. Do NOT invent or recall URLs from training data — any URL not in the materials above will be silently dropped from the user's citations list, leaving the bullet uncited.
- Do NOT emit `[N]` markers in the `text` field — the system appends them after parsing your output.
- End each line with `\n`. End your final bullet with `\n` as well.
```

- [ ] **Step 2: Verify the file substitutes correctly**

Run a one-off Python sanity check:

```bash
cd backend && python -c "
from string import Template
from pathlib import Path
t = Template(Path('research/overview/prompts/formatter_user_streaming.txt').read_text())
out = t.substitute(name='X', office='Y', breadth_block='B', depth_block='D')
assert 'Official: X' in out
assert 'Office: Y' in out
assert 'OUTPUT FORMAT (CRITICAL' in out
print('OK')
"
```

Expected: prints `OK` with no exception.

- [ ] **Step 3: Commit**

```bash
git add backend/research/overview/prompts/formatter_user_streaming.txt
git commit -m "feat(v4): add NDJSON-shape user prompt for streaming formatter"
```

---

## Task 5: Refactor formatter into dispatch + shared helpers

Lift the existing structured-output body into a private `_formatter_structured` so the dispatching `formatter()` can branch by env flag in later tasks. **No behavior change in this task** — just code reorganization. The streaming branch is a stub that delegates to the structured branch (so tests stay green) until Task 7 fills it in.

**Files:**
- Modify: `backend/research/overview/nodes/formatter.py`
- Test: `backend/tests/test_formatter_dispatch.py`

- [ ] **Step 1: Write the failing test for dispatch**

Create `backend/tests/test_formatter_dispatch.py`:

```python
"""Verify the formatter() top-level dispatch picks the right branch
based on OVERVIEW_V4_FORMATTER_STREAMING env var."""

import os
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_streaming_disabled_calls_structured_branch(monkeypatch):
    monkeypatch.delenv("OVERVIEW_V4_FORMATTER_STREAMING", raising=False)
    from research.overview.nodes import formatter as fmt

    with patch.object(fmt, "_formatter_structured", new=AsyncMock(return_value={"summary": None, "usage_log": []})) as mock_struct, \
         patch.object(fmt, "_formatter_streaming", new=AsyncMock(return_value={"summary": None, "usage_log": []})) as mock_stream:
        await fmt.formatter({"rep": None, "usage_log": []})

    mock_struct.assert_awaited_once()
    mock_stream.assert_not_awaited()


@pytest.mark.asyncio
async def test_streaming_enabled_calls_streaming_branch(monkeypatch):
    monkeypatch.setenv("OVERVIEW_V4_FORMATTER_STREAMING", "true")
    from research.overview.nodes import formatter as fmt

    with patch.object(fmt, "_formatter_structured", new=AsyncMock(return_value={"summary": None, "usage_log": []})) as mock_struct, \
         patch.object(fmt, "_formatter_streaming", new=AsyncMock(return_value={"summary": None, "usage_log": []})) as mock_stream:
        await fmt.formatter({"rep": None, "usage_log": []})

    mock_stream.assert_awaited_once()
    mock_struct.assert_not_awaited()


@pytest.mark.parametrize("val", ["1", "true", "TRUE", "yes", "on"])
def test_streaming_enabled_truthy_values(val, monkeypatch):
    monkeypatch.setenv("OVERVIEW_V4_FORMATTER_STREAMING", val)
    from research.overview.nodes.formatter import _streaming_enabled
    assert _streaming_enabled() is True


@pytest.mark.parametrize("val", ["", "0", "false", "no", "off", "anything"])
def test_streaming_disabled_falsy_values(val, monkeypatch):
    monkeypatch.setenv("OVERVIEW_V4_FORMATTER_STREAMING", val)
    from research.overview.nodes.formatter import _streaming_enabled
    assert _streaming_enabled() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && pytest tests/test_formatter_dispatch.py -v
```

Expected: FAIL — `_formatter_structured`, `_formatter_streaming`, `_streaming_enabled` don't exist.

- [ ] **Step 3: Refactor `formatter.py`**

In `backend/research/overview/nodes/formatter.py`:

(a) Add this helper after `_show_sources_enabled` (around line 51):

```python
def _streaming_enabled() -> bool:
    """Gate for the formatter streaming path. Read at call time so tests
    and env flips don't require a restart."""
    return os.getenv("OVERVIEW_V4_FORMATTER_STREAMING", "").strip().lower() in (
        "1", "true", "yes", "on"
    )
```

(b) Replace the existing `formatter` function (the `@observe(name="v4-formatter") async def formatter(state: V4State)` block, currently around lines 212-282) with:

```python
@observe(name="v4-formatter")
async def formatter(state: V4State) -> dict:
    """Format breadth + depth search results into bullets; assemble
    citations in python.

    Branches by OVERVIEW_V4_FORMATTER_STREAMING env var:
    - On  → ``_formatter_streaming``: NDJSON line stream, partials written
            to the store as each bullet lands.
    - Off → ``_formatter_structured``: existing single with_structured_output
            call with retry-on-ValidationError.
    """
    if _streaming_enabled():
        return await _formatter_streaming(state)
    return await _formatter_structured(state)


async def _formatter_structured(state: V4State) -> dict:
    """Original v4 formatter: one with_structured_output call returning
    parallel ``bullet_texts`` + ``bullet_sources`` lists. Retries once on
    Pydantic ValidationError; lets the second failure propagate so the
    pipeline marks the task failed (frontend then shows the error UI)."""
    rep = state["rep"]
    filtered = state.get("filtered_results") or []
    depth = state.get("depth_search_results") or []

    show_sources = _show_sources_enabled()
    if show_sources:
        before = len(depth)
        depth = _dedupe_depth_against_breadth(filtered, depth)
        logger.info(
            f"[v4] Formatter dedupe (show-sources on): depth {before} → "
            f"{len(depth)} after dropping URL collisions with breadth/depth"
        )

    breadth_block = _format_breadth_block(filtered)
    depth_block = _format_depth_block(depth)

    langfuse_handler = CallbackHandler()
    usage_tracker = UsageTracker()
    model = ChatAnthropic(
        model=_model_id(),
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    )
    structured = model.with_structured_output(_FormatterOutput).with_retry(
        retry_if_exception_type=(ValidationError,),
        stop_after_attempt=2,
    )

    system_template = Template((_PROMPTS_DIR / "formatter_system.txt").read_text())
    user_template = Template((_PROMPTS_DIR / "formatter_user.txt").read_text())
    system_prompt = system_template.substitute(current_date=date.today().isoformat())
    user_prompt = user_template.substitute(
        name=rep.name,
        office=rep.office,
        breadth_block=breadth_block,
        depth_block=depth_block,
    )

    result = await structured.ainvoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
        config={
            "callbacks": [langfuse_handler, usage_tracker],
            "run_name": f"v4:formatter:{rep.name}",
        },
    )

    pairs = _zip_bullets(result)
    citations, url_to_n = _build_citations(pairs, filtered + depth)
    bullet_texts = _attach_markers(pairs, url_to_n)
    sources = _build_sources(filtered + depth) if show_sources else []
    summary = ResearchSummary(
        bullets=bullet_texts, citations=citations, sources=sources
    )
    logger.info(
        f"[v4] Formatter (structured) for {rep.name}: {len(summary.bullets)} bullets / "
        f"{len(summary.citations)} citations / {len(summary.sources)} sources"
    )
    return {"summary": summary, "usage_log": [usage_tracker.stats]}


async def _formatter_streaming(state: V4State) -> dict:
    """NDJSON line-streaming formatter. Stub — implemented in Task 7.

    Until then, delegate to the structured branch so the dispatch is
    behaviorally a no-op when the env var flips on prematurely."""
    return await _formatter_structured(state)
```

- [ ] **Step 4: Run dispatch tests to verify they pass**

Run:

```bash
cd backend && pytest tests/test_formatter_dispatch.py -v
```

Expected: all 12 tests PASS (2 dispatch + 5 truthy + 5 falsy).

- [ ] **Step 5: Commit**

```bash
git add backend/research/overview/nodes/formatter.py backend/tests/test_formatter_dispatch.py
git commit -m "refactor(v4): split formatter into dispatch + structured branch"
```

---

## Task 6: Implement and test the line-parser helper

The streaming branch's hot loop is a `_handle_line` function that parses one NDJSON line into a bullet (or skips it). Build it test-first as a pure function so the integration test in Task 7 can focus on stream wiring.

**Files:**
- Modify: `backend/research/overview/nodes/formatter.py`
- Test: `backend/tests/test_formatter_handle_line.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_formatter_handle_line.py`:

```python
"""Pure-function tests for the streaming formatter's per-line handler.

The handler parses one NDJSON line, mutates running citation state, and
returns either a ready-to-render bullet string or None (skip)."""

import pytest

from models import Citation
from research.overview.models import SearchResult
from research.overview.nodes.formatter import _handle_streaming_line


def _pool() -> dict[str, SearchResult]:
    return {
        "https://a.com/x": SearchResult(url="https://a.com/x", title="A", snippet=""),
        "https://b.com/y": SearchResult(url="https://b.com/y", title="B", snippet=""),
        "https://c.com/z": SearchResult(url="https://c.com/z", title="C", snippet="", published_date="2025-03-01"),
    }


def test_well_formed_line_returns_bullet_with_marker():
    citations: list[Citation] = []
    url_to_n: dict[str, int] = {}
    pool = _pool()

    bullet = _handle_streaming_line(
        '{"text":"Hello world","sources":["https://a.com/x"]}',
        pool=pool, citations=citations, url_to_n=url_to_n,
    )

    assert bullet == "Hello world [1]"
    assert len(citations) == 1
    assert citations[0].url == "https://a.com/x"
    assert citations[0].title == "A"
    assert url_to_n == {"https://a.com/x": 1}


def test_blank_line_returns_none():
    bullet = _handle_streaming_line("", pool={}, citations=[], url_to_n={})
    assert bullet is None
    bullet = _handle_streaming_line("   ", pool={}, citations=[], url_to_n={})
    assert bullet is None


def test_malformed_json_returns_none():
    bullet = _handle_streaming_line(
        '{"text":"oops"', pool={}, citations=[], url_to_n={},
    )
    assert bullet is None


def test_missing_text_field_returns_none():
    bullet = _handle_streaming_line(
        '{"sources":["https://a.com/x"]}', pool=_pool(), citations=[], url_to_n={},
    )
    assert bullet is None


def test_missing_sources_field_returns_none():
    bullet = _handle_streaming_line(
        '{"text":"hi"}', pool={}, citations=[], url_to_n={},
    )
    assert bullet is None


def test_wrong_type_for_sources_returns_none():
    bullet = _handle_streaming_line(
        '{"text":"hi","sources":"not-a-list"}',
        pool={}, citations=[], url_to_n={},
    )
    assert bullet is None


def test_empty_text_returns_none():
    bullet = _handle_streaming_line(
        '{"text":"   ","sources":[]}', pool={}, citations=[], url_to_n={},
    )
    assert bullet is None


def test_url_not_in_pool_dropped_silently():
    citations: list[Citation] = []
    url_to_n: dict[str, int] = {}

    bullet = _handle_streaming_line(
        '{"text":"Hi","sources":["https://hallucinated.com/x"]}',
        pool=_pool(), citations=citations, url_to_n=url_to_n,
    )

    assert bullet == "Hi"  # no marker, no citation
    assert citations == []
    assert url_to_n == {}


def test_dedup_url_across_calls_reuses_same_n():
    citations: list[Citation] = []
    url_to_n: dict[str, int] = {}
    pool = _pool()

    b1 = _handle_streaming_line(
        '{"text":"first","sources":["https://a.com/x"]}',
        pool=pool, citations=citations, url_to_n=url_to_n,
    )
    b2 = _handle_streaming_line(
        '{"text":"second","sources":["https://a.com/x","https://b.com/y"]}',
        pool=pool, citations=citations, url_to_n=url_to_n,
    )

    assert b1 == "first [1]"
    assert b2 == "second [1][2]"
    assert len(citations) == 2  # not 3


def test_multiple_sources_yield_sorted_markers():
    citations: list[Citation] = []
    url_to_n: dict[str, int] = {}
    pool = _pool()

    # Pre-seed with B already registered as 1, A registered next as 2.
    _handle_streaming_line(
        '{"text":"seed","sources":["https://b.com/y","https://a.com/x"]}',
        pool=pool, citations=citations, url_to_n=url_to_n,
    )
    # Now a bullet citing both should render markers in N-sorted order [1][2].
    bullet = _handle_streaming_line(
        '{"text":"both","sources":["https://a.com/x","https://b.com/y"]}',
        pool=pool, citations=citations, url_to_n=url_to_n,
    )
    assert bullet == "both [1][2]"


def test_published_date_propagates_to_citation():
    citations: list[Citation] = []
    url_to_n: dict[str, int] = {}
    pool = _pool()

    _handle_streaming_line(
        '{"text":"hi","sources":["https://c.com/z"]}',
        pool=pool, citations=citations, url_to_n=url_to_n,
    )
    assert citations[0].published_date == "2025-03-01"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend && pytest tests/test_formatter_handle_line.py -v
```

Expected: FAIL with `ImportError: cannot import name '_handle_streaming_line'`.

- [ ] **Step 3: Implement `_handle_streaming_line`**

In `backend/research/overview/nodes/formatter.py`, add this function near the other helpers (after `_attach_markers`, around line 210, before the `@observe(name="v4-formatter")` decorator):

```python
def _handle_streaming_line(
    line: str,
    *,
    pool: dict[str, SearchResult],
    citations: list[Citation],
    url_to_n: dict[str, int],
) -> str | None:
    """Parse one NDJSON line into a ready-to-render bullet string.

    Returns the bullet (with ``[N1][N2]...`` markers appended) on success,
    or ``None`` if the line is blank, malformed, wrong-shape, or has empty
    text. Mutates ``citations`` and ``url_to_n`` in place when new URLs
    are seen.

    URLs not in ``pool`` are dropped silently with a warning log — same
    philosophy as ``_build_citations`` in the structured-output path.
    """
    line = line.strip()
    if not line:
        return None

    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        logger.warning(f"[v4] streaming: malformed JSON line, skipping: {line[:120]!r}")
        return None

    if not isinstance(obj, dict):
        logger.warning(f"[v4] streaming: non-dict line, skipping: {line[:120]!r}")
        return None

    text = obj.get("text")
    sources = obj.get("sources")
    if not isinstance(text, str) or not isinstance(sources, list):
        logger.warning(
            f"[v4] streaming: bad shape (text={type(text).__name__}, "
            f"sources={type(sources).__name__}), skipping: {line[:120]!r}"
        )
        return None

    text = text.strip()
    if not text:
        return None

    for url in sources:
        if not isinstance(url, str) or not url or url in url_to_n:
            continue
        sr = pool.get(url)
        if sr is None:
            logger.warning(
                f"[v4] streaming: cited URL not in breadth+depth pool, dropping: {url}"
            )
            continue
        title = sr.title or url
        published = sr.published_date or None
        citations.append(Citation(title=title, url=url, published_date=published))
        url_to_n[url] = len(citations)

    ns = sorted({url_to_n[u] for u in sources if isinstance(u, str) and u in url_to_n})
    marker = "".join(f"[{n}]" for n in ns)
    return f"{text} {marker}".rstrip() if marker else text
```

Also add `import json` to the imports at the top of `formatter.py` (after `import logging`):

```python
import json
import logging
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd backend && pytest tests/test_formatter_handle_line.py -v
```

Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/research/overview/nodes/formatter.py backend/tests/test_formatter_handle_line.py
git commit -m "feat(v4): add _handle_streaming_line NDJSON parser helper"
```

---

## Task 7: Implement `_formatter_streaming` and integration-test it

Replace the stub from Task 5 with the real streaming implementation. Test it with a fake `astream` that yields a recorded chunk sequence.

**Files:**
- Modify: `backend/research/overview/nodes/formatter.py`
- Test: `backend/tests/test_formatter_streaming.py`

- [ ] **Step 1: Write the failing integration test**

Create `backend/tests/test_formatter_streaming.py`:

```python
"""End-to-end test for the streaming formatter branch.

Patches ChatAnthropic to return a fake stream of AIMessageChunks that
mimic Sonnet emitting NDJSON. Verifies:
- partials are written to the store as bullets land
- final summary has all bullets with [N] markers attached
- citations are deduped across bullets
- min-bullets threshold triggers a RuntimeError when too few valid
  bullets emerged
"""

from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessageChunk

from models import Representative
from research.overview.models import SearchResult
from research.overview.nodes import formatter as fmt
from store.research_store import InMemoryResearchStore


def _rep() -> Representative:
    return Representative(name="Jane Doe", office="US Senator", contact={})


def _filtered() -> list[SearchResult]:
    return [
        SearchResult(url="https://a.com/x", title="Article A", snippet="snippet a"),
        SearchResult(url="https://b.com/y", title="Article B", snippet="snippet b"),
        SearchResult(url="https://c.com/z", title="Article C", snippet="snippet c"),
    ]


def _chunks(text: str):
    """Yield one AIMessageChunk per ~10 chars to simulate token streaming."""
    for i in range(0, len(text), 10):
        yield AIMessageChunk(content=text[i:i + 10])


class _FakeChatAnthropic:
    """Stand-in for ChatAnthropic that records calls and yields a
    pre-canned chunk stream."""

    def __init__(self, *_args, stream_text: str = "", **_kwargs):
        self._stream_text = stream_text

    async def astream(self, _messages, config=None):
        for chunk in _chunks(self._stream_text):
            yield chunk


@pytest.mark.asyncio
async def test_streaming_writes_partials_and_final(monkeypatch):
    monkeypatch.setenv("OVERVIEW_V4_FORMATTER_STREAMING", "true")

    store = InMemoryResearchStore()
    from research.overview.models import ResearchSummary
    await store.create("rid", total_sections=1, summary=ResearchSummary())

    stream_text = (
        '{"text":"Bullet one about A","sources":["https://a.com/x"]}\n'
        '{"text":"Bullet two about A and B","sources":["https://a.com/x","https://b.com/y"]}\n'
        '{"text":"Bullet three about C","sources":["https://c.com/z"]}\n'
    )

    snapshots: list[list[str]] = []
    real_update = store.update_partial

    async def spy_update(rid, summary):
        snapshots.append(list(summary.bullets))
        await real_update(rid, summary)

    store.update_partial = spy_update  # type: ignore[method-assign]

    state = {
        "rep": _rep(),
        "filtered_results": _filtered(),
        "depth_search_results": [],
        "store": store,
        "research_id": "rid",
        "usage_log": [],
    }

    def fake_chat(*args, **kwargs):
        return _FakeChatAnthropic(stream_text=stream_text)

    with patch("research.overview.nodes.formatter.ChatAnthropic", fake_chat):
        result = await fmt._formatter_streaming(state)

    summary = result["summary"]
    assert summary is not None
    assert summary.bullets == [
        "Bullet one about A [1]",
        "Bullet two about A and B [1][2]",
        "Bullet three about C [3]",
    ]
    assert [c.url for c in summary.citations] == [
        "https://a.com/x",
        "https://b.com/y",
        "https://c.com/z",
    ]
    # 3 partial writes happened, monotonically growing.
    assert len(snapshots) == 3
    assert snapshots[0] == ["Bullet one about A [1]"]
    assert len(snapshots[1]) == 2
    assert len(snapshots[2]) == 3


@pytest.mark.asyncio
async def test_streaming_skips_malformed_lines(monkeypatch):
    monkeypatch.setenv("OVERVIEW_V4_FORMATTER_STREAMING", "true")
    store = InMemoryResearchStore()
    from research.overview.models import ResearchSummary
    await store.create("rid", total_sections=1, summary=ResearchSummary())

    stream_text = (
        '{"text":"Good one","sources":["https://a.com/x"]}\n'
        'NOT JSON AT ALL\n'
        '{"text":"another","sources":["https://b.com/y"]}\n'
        '{"text":"third","sources":["https://c.com/z"]}\n'
    )

    state = {
        "rep": _rep(),
        "filtered_results": _filtered(),
        "depth_search_results": [],
        "store": store,
        "research_id": "rid",
        "usage_log": [],
    }

    def fake_chat(*args, **kwargs):
        return _FakeChatAnthropic(stream_text=stream_text)

    with patch("research.overview.nodes.formatter.ChatAnthropic", fake_chat):
        result = await fmt._formatter_streaming(state)

    # Three valid bullets parsed, malformed line skipped.
    assert len(result["summary"].bullets) == 3


@pytest.mark.asyncio
async def test_streaming_drains_trailing_line_without_newline(monkeypatch):
    monkeypatch.setenv("OVERVIEW_V4_FORMATTER_STREAMING", "true")
    store = InMemoryResearchStore()
    from research.overview.models import ResearchSummary
    await store.create("rid", total_sections=1, summary=ResearchSummary())

    # No trailing newline on the last bullet.
    stream_text = (
        '{"text":"one","sources":["https://a.com/x"]}\n'
        '{"text":"two","sources":["https://b.com/y"]}\n'
        '{"text":"three","sources":["https://c.com/z"]}'
    )

    state = {
        "rep": _rep(),
        "filtered_results": _filtered(),
        "depth_search_results": [],
        "store": store,
        "research_id": "rid",
        "usage_log": [],
    }

    def fake_chat(*args, **kwargs):
        return _FakeChatAnthropic(stream_text=stream_text)

    with patch("research.overview.nodes.formatter.ChatAnthropic", fake_chat):
        result = await fmt._formatter_streaming(state)

    assert len(result["summary"].bullets) == 3


@pytest.mark.asyncio
async def test_streaming_min_bullets_threshold_raises(monkeypatch):
    monkeypatch.setenv("OVERVIEW_V4_FORMATTER_STREAMING", "true")
    monkeypatch.setenv("OVERVIEW_V4_FORMATTER_MIN_BULLETS", "3")

    store = InMemoryResearchStore()
    from research.overview.models import ResearchSummary
    await store.create("rid", total_sections=1, summary=ResearchSummary())

    # Only 2 valid bullets; threshold is 3 → must raise.
    stream_text = (
        '{"text":"one","sources":["https://a.com/x"]}\n'
        '{"text":"two","sources":["https://b.com/y"]}\n'
    )

    state = {
        "rep": _rep(),
        "filtered_results": _filtered(),
        "depth_search_results": [],
        "store": store,
        "research_id": "rid",
        "usage_log": [],
    }

    def fake_chat(*args, **kwargs):
        return _FakeChatAnthropic(stream_text=stream_text)

    with patch("research.overview.nodes.formatter.ChatAnthropic", fake_chat):
        with pytest.raises(RuntimeError, match="too few valid bullets"):
            await fmt._formatter_streaming(state)


@pytest.mark.asyncio
async def test_streaming_works_without_store(monkeypatch):
    """If state lacks store/research_id (e.g. a direct call from a script
    or a test), streaming should still produce a final summary; just no
    partial writes."""
    monkeypatch.setenv("OVERVIEW_V4_FORMATTER_STREAMING", "true")

    stream_text = (
        '{"text":"a","sources":["https://a.com/x"]}\n'
        '{"text":"b","sources":["https://b.com/y"]}\n'
        '{"text":"c","sources":["https://c.com/z"]}\n'
    )

    state = {
        "rep": _rep(),
        "filtered_results": _filtered(),
        "depth_search_results": [],
        "usage_log": [],
        # no "store" / "research_id"
    }

    def fake_chat(*args, **kwargs):
        return _FakeChatAnthropic(stream_text=stream_text)

    with patch("research.overview.nodes.formatter.ChatAnthropic", fake_chat):
        result = await fmt._formatter_streaming(state)

    assert len(result["summary"].bullets) == 3


@pytest.mark.asyncio
async def test_streaming_populates_sources_when_show_sources_on(monkeypatch):
    monkeypatch.setenv("OVERVIEW_V4_FORMATTER_STREAMING", "true")
    monkeypatch.setenv("OVERVIEW_V4_SHOW_SOURCES", "true")

    store = InMemoryResearchStore()
    from research.overview.models import ResearchSummary
    await store.create("rid", total_sections=1, summary=ResearchSummary())

    stream_text = (
        '{"text":"a","sources":["https://a.com/x"]}\n'
        '{"text":"b","sources":["https://b.com/y"]}\n'
        '{"text":"c","sources":["https://c.com/z"]}\n'
    )

    state = {
        "rep": _rep(),
        "filtered_results": _filtered(),
        "depth_search_results": [],
        "store": store,
        "research_id": "rid",
        "usage_log": [],
    }

    def fake_chat(*args, **kwargs):
        return _FakeChatAnthropic(stream_text=stream_text)

    with patch("research.overview.nodes.formatter.ChatAnthropic", fake_chat):
        result = await fmt._formatter_streaming(state)

    # All 3 pool entries land in `sources` (deduped, breadth+depth combined).
    assert len(result["summary"].sources) == 3
    # And the store's final task summary has them too.
    final = (await store.get("rid")).summary
    assert len(final.sources) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend && pytest tests/test_formatter_streaming.py -v
```

Expected: FAIL — the streaming function is still the stub from Task 5 that delegates to structured (which would call the real Anthropic API).

- [ ] **Step 3: Implement `_formatter_streaming`**

In `backend/research/overview/nodes/formatter.py`, add a `_min_bullets` helper near the top with the other env-reading helpers (after `_streaming_enabled`):

```python
def _min_bullets() -> int:
    """Threshold below which a streaming run is treated as a failure.
    The structured branch had Pydantic validation; streaming has only
    per-line tolerance, so we add a sanity check on total count."""
    return int(os.getenv("OVERVIEW_V4_FORMATTER_MIN_BULLETS", "3"))
```

Then **replace** the stub `_formatter_streaming` (the one added in Task 5 that delegates to `_formatter_structured`) with the real implementation:

```python
async def _formatter_streaming(state: V4State) -> dict:
    """NDJSON line-streaming formatter.

    Streams ``ChatAnthropic.astream``, splits on ``\\n``, parses each line
    as ``{"text":..., "sources":[...]}``, builds running citations + ``[N]``
    markers, and writes the growing summary to the store after every new
    bullet. Lets a fatal stream-level exception propagate; raises
    ``RuntimeError`` if fewer than ``OVERVIEW_V4_FORMATTER_MIN_BULLETS``
    valid bullets emerged so the pipeline marks the task failed.
    """
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
            f"[v4] Formatter dedupe (show-sources on): depth {before} → "
            f"{len(depth)} after dropping URL collisions with breadth/depth"
        )

    breadth_block = _format_breadth_block(filtered)
    depth_block = _format_depth_block(depth)
    pool: list[SearchResult] = filtered + depth
    pool_by_url: dict[str, SearchResult] = {r.url: r for r in pool if r.url}
    sources = _build_sources(pool) if show_sources else []

    langfuse_handler = CallbackHandler()
    usage_tracker = UsageTracker()
    model = ChatAnthropic(
        model=_model_id(),
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    )

    system_template = Template((_PROMPTS_DIR / "formatter_system.txt").read_text())
    user_template = Template(
        (_PROMPTS_DIR / "formatter_user_streaming.txt").read_text()
    )
    system_prompt = system_template.substitute(current_date=date.today().isoformat())
    user_prompt = user_template.substitute(
        name=rep.name,
        office=rep.office,
        breadth_block=breadth_block,
        depth_block=depth_block,
    )

    bullets: list[str] = []
    citations: list[Citation] = []
    url_to_n: dict[str, int] = {}
    line_buffer = ""
    n_chunks = 0

    async def _flush_line(line: str) -> None:
        bullet = _handle_streaming_line(
            line, pool=pool_by_url, citations=citations, url_to_n=url_to_n,
        )
        if bullet is None:
            return
        bullets.append(bullet)
        if store is not None and research_id is not None:
            partial = ResearchSummary(
                bullets=list(bullets),
                citations=list(citations),
                sources=sources,
            )
            await store.update_partial(research_id, partial)

    async for chunk in model.astream(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
        config={
            "callbacks": [langfuse_handler, usage_tracker],
            "run_name": f"v4:formatter:{rep.name}",
        },
    ):
        n_chunks += 1
        content = chunk.content
        # ChatAnthropic chunks are str, but the type union allows list — coerce.
        if not isinstance(content, str):
            content = "" if content is None else str(content)
        line_buffer += content
        while "\n" in line_buffer:
            line, line_buffer = line_buffer.split("\n", 1)
            await _flush_line(line)

    # Drain any trailing partial line (LLM didn't end with \n).
    if line_buffer.strip():
        await _flush_line(line_buffer)

    if len(bullets) < _min_bullets():
        raise RuntimeError(
            f"formatter produced too few valid bullets: "
            f"{len(bullets)} < {_min_bullets()}"
        )

    summary = ResearchSummary(
        bullets=bullets, citations=citations, sources=sources
    )
    logger.info(
        f"[v4] Formatter (streaming) for {rep.name}: {len(bullets)} bullets / "
        f"{len(citations)} citations / {len(sources)} sources / {n_chunks} chunks"
    )
    return {"summary": summary, "usage_log": [usage_tracker.stats]}
```

- [ ] **Step 4: Run streaming tests to verify they pass**

Run:

```bash
cd backend && pytest tests/test_formatter_streaming.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Run full backend test suite**

Run:

```bash
cd backend && pytest -v
```

Expected: all tests across all files PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/research/overview/nodes/formatter.py backend/tests/test_formatter_streaming.py
git commit -m "feat(v4): implement NDJSON-streaming formatter branch with per-bullet store partials"
```

---

## Task 8: Frontend — `ResearchContent` accepts `status` prop with trailer skeleton

Add a `status` prop to the bullets renderer; render a small trailer skeleton below completed bullets while `status === "loading"`.

**Files:**
- Modify: `frontend/src/components/overview/bullets/ResearchContent.tsx`
- Modify: `frontend/src/components/overview/index.tsx`

- [ ] **Step 1: Update the BulletsResearchContent component**

Replace the entire contents of `frontend/src/components/overview/bullets/ResearchContent.tsx` with:

```tsx
/**
 * Bullets research content renderer — single blended bullet list with
 * inline citation markers resolved against a unified citation pool.
 *
 * Used by any overview pipeline version that produces a BulletsResearchSummary
 * (the default pipeline plus legacy v2/v3). When the default pipeline emits
 * ``sources`` (gated on the ``OVERVIEW_V4_SHOW_SOURCES`` backend flag), an
 * expandable "Further reading (N)" list renders below the bullets — a
 * jumping-off point for the user's own research, distinct from the inline
 * citation markers (which exist to back up the bullets themselves).
 *
 * When ``status === "loading"`` and bullets are present, a small trailer
 * skeleton renders below the bullet list to signal "more coming" — this
 * is the visual cue for the v4 streaming-formatter path.
 */

import type { BulletsResearchSummary } from "./types";
import { FurtherReading } from "@/components/FurtherReading";
import { renderInline } from "@/components/overview/renderInline";
import { Skeleton } from "@/components/ui/skeleton";

function BulletsSkeleton() {
  return (
    <div className="space-y-2 mt-1">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="space-y-1">
          <Skeleton className="h-3.5 w-5/6" />
          <Skeleton className="h-3.5 w-3/4" />
        </div>
      ))}
    </div>
  );
}

function BulletsTrailerSkeleton() {
  return (
    <div className="space-y-2 pl-5 mt-2" aria-label="More bullets streaming">
      {Array.from({ length: 2 }).map((_, i) => (
        <div key={i} className="space-y-1">
          <Skeleton className="h-3 w-5/6" />
          <Skeleton className="h-3 w-2/3" />
        </div>
      ))}
    </div>
  );
}

export function ResearchContent({
  summary,
  status,
}: {
  summary: BulletsResearchSummary;
  status?: "loading" | "complete" | "failed" | "idle";
}) {
  const { bullets, citations, sources } = summary;

  // Empty bullets = task hasn't written synthesis yet; parent's loading message
  // ("Scraping the web...") is the primary indicator — full skeleton is the filler.
  if (bullets.length === 0) {
    return (
      <div className="space-y-2 text-sm leading-relaxed prose prose-sm prose-neutral dark:prose-invert max-w-none">
        <BulletsSkeleton />
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

- [ ] **Step 2: Update the dispatcher in overview/index.tsx**

Replace the entire contents of `frontend/src/components/overview/index.tsx` with:

```tsx
/**
 * Overview dispatch: the backend may return a v1 sectioned summary OR a
 * BulletsResearchSummary (v2, v3, v4). Consumers get a single ResearchContent
 * component and a union type; the component picks a renderer at runtime
 * based on the response shape.
 *
 * Optional ``status`` is forwarded to the bullets renderer so the v4
 * streaming-formatter path can render a trailer skeleton while bullets
 * are still arriving.
 */

import type { ResearchSummary as V1ResearchSummary } from "./v1";
import type { BulletsResearchSummary } from "./bullets";
import { ResearchContent as V1ResearchContent } from "./v1";
import { ResearchContent as BulletsResearchContent } from "./bullets";

export type ResearchSummary = V1ResearchSummary | BulletsResearchSummary;

export function isBullets(summary: ResearchSummary): summary is BulletsResearchSummary {
  return "bullets" in summary;
}

export function ResearchContent({
  summary,
  status,
}: {
  summary: ResearchSummary;
  status?: "loading" | "complete" | "failed" | "idle";
}) {
  if (isBullets(summary)) {
    return <BulletsResearchContent summary={summary} status={status} />;
  }
  return <V1ResearchContent summary={summary} />;
}
```

- [ ] **Step 3: Type-check**

Run:

```bash
cd frontend && npx tsc --noEmit
```

Expected: no type errors. (Existing callers don't pass `status`, but that's fine — the prop is optional.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/overview/bullets/ResearchContent.tsx frontend/src/components/overview/index.tsx
git commit -m "feat(frontend): add status prop and trailer skeleton to bullets renderer"
```

---

## Task 9: Pass `status` from `RepCard` and `CandidateCard` into `ResearchContent`

**Files:**
- Modify: `frontend/src/components/RepCard.tsx`
- Modify: `frontend/src/components/CandidateCard.tsx`

- [ ] **Step 1: Update RepCard to pass status**

In `frontend/src/components/RepCard.tsx`:

(a) On line 133 (inside the `loading && summary` block), change:

```tsx
              <ResearchContent summary={summary} />
```

to:

```tsx
              <ResearchContent summary={summary} status={researchStatus} />
```

(b) On line 160 (inside the `complete && summary` block), change:

```tsx
                <ResearchContent summary={summary} />
```

to:

```tsx
                <ResearchContent summary={summary} status={researchStatus} />
```

- [ ] **Step 2: Update CandidateCard to pass status**

In `frontend/src/components/CandidateCard.tsx`, on lines 102 and 115, replace each:

```tsx
              <ResearchContent summary={summary} />
```

with:

```tsx
              <ResearchContent summary={summary} status={researchStatus} />
```

- [ ] **Step 3: Type-check**

Run:

```bash
cd frontend && npx tsc --noEmit
```

Expected: no type errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/RepCard.tsx frontend/src/components/CandidateCard.tsx
git commit -m "feat(frontend): pass research status into ResearchContent for streaming trailer"
```

---

## Task 10: Update CLAUDE.md with new env vars and pipeline notes

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add new env vars to the env-var section**

In `CLAUDE.md`, find the `OVERVIEW_V4_FORMATTER_MODEL` line in the Environment Variables section. After the line:

```
- `OVERVIEW_V4_FORMATTER_MODEL` — v4 only: model ID for the formatter node. Falls back to `CLAUDE_MODEL`. Formatter is the second-biggest latency contributor in v4 (~26s with 23k input tokens), so smaller-model A/B is high-leverage.
```

Add two new bullets:

```
- `OVERVIEW_V4_FORMATTER_STREAMING` — v4 only: when `true`, the formatter switches from a single `with_structured_output` call to NDJSON line streaming via `ChatAnthropic.astream`. Each completed bullet is parsed, marked with `[N]` citations, and written to `InMemoryResearchStore` via the new `update_partial()` method as it lands; the existing 2s frontend poll picks up partials so the user sees the first bullet in ~5–8s instead of waiting ~22s for the full block. When `false` (default), the structured-output path runs unchanged. Reverting the streaming path is a single env-var flip — no code change.
- `OVERVIEW_V4_FORMATTER_MIN_BULLETS` — v4 only: minimum number of well-formed bullets the streaming formatter must emit before the run is considered successful (default `3`). Below this, the formatter raises `RuntimeError`, the pipeline returns `(None, total)`, the router marks the task `failed`, and the frontend shows the "Research unavailable" UI. Replaces the Pydantic schema validation that the structured-output path got from `with_structured_output`.
```

- [ ] **Step 2: Update the formatter description in the v4 default section**

In `CLAUDE.md`, find the long paragraph starting `- **Default** (`research/overview/`)` (around the part describing the formatter). Locate the sentence ending with `...the second attempt usually emits the correct shape.` After it, add:

```
 An optional NDJSON line-streaming variant runs when `OVERVIEW_V4_FORMATTER_STREAMING=true` (uses `formatter_user_streaming.txt`, `ChatAnthropic.astream`, and the new `InMemoryResearchStore.update_partial()` method) — the user sees the first bullet in ~5–8s instead of waiting for the full block.
```

- [ ] **Step 3: Update the trace-names section**

In `CLAUDE.md`, the v4 trace-name bullet currently mentions `v4-formatter`. No change needed — the `@observe(name="v4-formatter")` decorator still wraps both branches.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude.md): document formatter streaming env vars and pipeline path"
```

---

## Task 11: Manual end-to-end smoke test

Per CLAUDE.md, "for UI or frontend changes, start the dev server and use the feature in a browser before reporting the task as complete." Validate the streaming path against a real rep before declaring done.

**Files:** None — this is verification only.

- [ ] **Step 1: Start the backend with streaming enabled**

In one terminal:

```bash
cd backend && OVERVIEW_V4_FORMATTER_STREAMING=true uvicorn main:app --reload
```

Expected: server starts on `:8000` without errors.

- [ ] **Step 2: Start the frontend**

In a second terminal:

```bash
cd frontend && npm run dev
```

Expected: Vite dev server starts on `:5173`.

- [ ] **Step 3: Run a rep lookup and trigger AI overview**

Open `http://localhost:5173`, enter an address, click "Generate AI Overview" on one rep. Watch the browser:

- First bullet should appear in **<10s** (target: ~5–8s).
- Subsequent bullets stream in over the next ~5–10s.
- A small trailer skeleton (2 short rows) appears below the latest bullet while loading.
- "Further reading" list (if `OVERVIEW_V4_SHOW_SOURCES=true`) appears with the first bullet.
- When the run completes, the trailer skeleton disappears.

If any of those don't hold, **debug before continuing**. Check Langfuse traces for the `v4-formatter` span — should now show streaming-style output.

- [ ] **Step 4: Test the failure path**

Restart the backend with a deliberately impossible threshold:

```bash
cd backend && OVERVIEW_V4_FORMATTER_STREAMING=true OVERVIEW_V4_FORMATTER_MIN_BULLETS=99 uvicorn main:app --reload
```

Trigger an AI overview again. Expected: after ~25–30s the UI shows "Research unavailable for this representative" + a Retry button. **Not** a stuck-forever skeleton.

- [ ] **Step 5: Test the fallback path**

Restart with streaming off:

```bash
cd backend && uvicorn main:app --reload
```

Trigger an AI overview. Expected: behaves exactly like before this PR — single block of bullets appears after ~25s, no trailer skeleton during loading.

- [ ] **Step 6: Update the V4_PERFORMANCE doc with a postmortem**

In `docs/initiatives/V4_PERFORMANCE.md`, find the formatter section's bullet:

```
- [ ] **[L]** Stream the bullets so the user sees the first 1–2 within a few seconds rather than waiting 26s for the full block
```

Change it to `[x]` and append a one-paragraph postmortem with:
- Observed latency-to-first-bullet (from your manual run above).
- Observed latency-to-final-bullet.
- Any quality observations vs. the structured path (bullet count, citation count).
- Date shipped: `2026-05-12`.

Also remove the corresponding line from the "pivot to" list near the top of the doc:

```
> 1. **Streaming the formatter output** (open `[L]` item) — perceived-latency win without quality cost. User sees first bullets in ~5–8s instead of waiting 22s for the full block.
```

- [ ] **Step 7: Commit the postmortem**

```bash
git add docs/initiatives/V4_PERFORMANCE.md
git commit -m "docs(v4-perf): mark formatter streaming shipped, record observed latencies"
```

---

## Self-Review Notes (for the implementing engineer)

This plan was reviewed against the spec at write-time. A few invariants to preserve as you implement:

- **`@observe(name="v4-formatter")` stays on the dispatching `formatter()`** — both branches must trace under the same span name so Langfuse history continues unbroken.
- **`store.complete()` is still called from `pipeline.research_representative` after `ainvoke()`** — the streaming branch doesn't call it itself. The terminal write is whoever ran last (the structured-path nothing wrote; the streaming path's last `update_partial`); `complete()` then ratifies the final state.
- **The structured branch must remain byte-for-byte equivalent in behavior** to the pre-PR formatter when `OVERVIEW_V4_FORMATTER_STREAMING` is off. Task 5's refactor is the only change to that path; tasks 6–7 only add the streaming branch.
- **All shared helpers stay at module level** in `formatter.py` (`_format_breadth_block`, `_format_depth_block`, `_build_sources`, `_show_sources_enabled`, `_dedupe_depth_against_breadth`, `_model_id`, `_zip_bullets`, `_build_citations`, `_attach_markers`). Both branches use them.
- **`_FormatterOutput` Pydantic model stays** — used only by the structured branch but unchanged in shape.

If any test reveals a contradiction with the spec, stop and re-read the spec before changing the test.
