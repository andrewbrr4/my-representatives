# Rep Overview v4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the v4 rep-overview pipeline as a LangGraph-native StateGraph with breadth-first search, an adaptive-depth research subgraph, and a final formatter — fully isolated state across subgraph boundaries to prevent token accumulation.

**Architecture:** Five top-level nodes (`query_generator → breadth_search → filter → research_agent → formatter`). The research_agent is a compiled StateGraph subgraph with one tool, `request_depth_research`, which itself invokes a second compiled subgraph (depth_subgraph) with isolated `DepthState`. State updates from tools happen via `Command(update=...)`. Citations are assembled in Python from findings — never round-tripped through the formatter LLM.

**Tech Stack:** LangGraph (`StateGraph`, `ToolNode`, `Command`, `add_messages`), LangChain Anthropic, Tavily, Pydantic, Langfuse `@observe`, asyncio.

**Testing approach (codebase-specific):** This codebase has no pytest infrastructure (per CLAUDE.md, testing is via `backend/test_clients.ipynb`). Each task uses Python `-c` smoke tests for imports/instantiation, then a final integration task runs the full pipeline against a real rep with the running backend. Do NOT add a pytest framework as part of this plan.

**Reference spec:** `docs/superpowers/specs/2026-04-25-rep-overview-v4-design.md`

**Working directory:** All file paths are absolute. Run commands from `/Users/andrewbarry/projects/my-representatives` unless noted. Backend Python uses the `my-reps` conda env (`conda activate my-reps`) and runs out of `backend/` (imports are bare module names, not relative).

---

## File Plan

Files this plan creates:

```
backend/research/overview/v4/
├── __init__.py
├── pipeline.py
├── state.py
├── models.py
├── nodes/
│   ├── __init__.py
│   ├── query_generator.py
│   ├── breadth_search.py
│   ├── filter_node.py
│   ├── research_agent.py
│   ├── depth_subgraph.py
│   └── formatter.py
├── tools/
│   ├── __init__.py
│   ├── tavily_search.py
│   └── request_depth.py
└── prompts/
    ├── query_gen_system.txt
    ├── query_gen_user.txt
    ├── research_agent_system.txt
    ├── research_agent_user.txt
    ├── depth_agent_system.txt
    ├── depth_agent_user.txt
    ├── formatter_system.txt
    └── formatter_user.txt
```

Files this plan modifies:

- `backend/research/overview/__init__.py` — add `v4` branch to the version dispatch.
- `CLAUDE.md` — append v4 description, env vars, trace names.
- `docs/rep-overview-versions.md` — append a v4 section.

---

## Task 1: Create v4 directory skeleton

**Files:**
- Create: `backend/research/overview/v4/__init__.py`
- Create: `backend/research/overview/v4/nodes/__init__.py`
- Create: `backend/research/overview/v4/tools/__init__.py`
- Create: `backend/research/overview/v4/prompts/` (directory only)

- [ ] **Step 1: Create the directories**

```bash
mkdir -p /Users/andrewbarry/projects/my-representatives/backend/research/overview/v4/nodes
mkdir -p /Users/andrewbarry/projects/my-representatives/backend/research/overview/v4/tools
mkdir -p /Users/andrewbarry/projects/my-representatives/backend/research/overview/v4/prompts
```

- [ ] **Step 2: Create empty `__init__.py` files**

Write to `backend/research/overview/v4/__init__.py`:

```python
"""v4 overview pipeline — LangGraph-native breadth-first + adaptive-depth.

Exports the v3-compatible contract: ``ResearchSummary``,
``research_representative``, and ``TOTAL_SECTIONS``. Wired in this file
once ``pipeline.py`` and ``models.py`` exist (see later tasks).
"""
```

Write to `backend/research/overview/v4/nodes/__init__.py`:

```python
```

Write to `backend/research/overview/v4/tools/__init__.py`:

```python
```

- [ ] **Step 3: Verify the package imports**

```bash
cd /Users/andrewbarry/projects/my-representatives/backend && conda run -n my-reps python -c "import research.overview.v4; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
cd /Users/andrewbarry/projects/my-representatives
git add backend/research/overview/v4/__init__.py backend/research/overview/v4/nodes/__init__.py backend/research/overview/v4/tools/__init__.py
git commit -m "v4: scaffold package skeleton"
```

---

## Task 2: Define v4 models (Finding, SearchResult, ResearchSummary)

**Files:**
- Create: `backend/research/overview/v4/models.py`

The v4 package owns `Finding`, `SearchResult`, and `ResearchSummary`. `Citation` is reused from `backend/models.py` (same as v3). `BulletList` is reused from `backend/research/overview/_bullet_coercion.py` (same as v3) — this is the typed list that transparently coerces Anthropic's occasional stringified-JSON-array mistake.

- [ ] **Step 1: Write `models.py`**

Write to `backend/research/overview/v4/models.py`:

```python
"""v4 overview output schema and internal types.

``ResearchSummary`` matches the frontend ``BulletsResearchSummary`` contract
(same shape as v2/v3): ``bullets: list[str]`` (required, non-nullable —
empty list = loading state) plus ``citations: list[Citation]``.

``Finding`` and ``SearchResult`` are internal to v4 and shuttle data
between nodes. Both intentionally lightweight to keep token footprint
predictable across the pipeline.
"""

from pydantic import BaseModel, Field

from models import Citation
from research.overview._bullet_coercion import BulletList


class SearchResult(BaseModel):
    """Single Tavily search result. Mirrors the dict shape returned by
    ``research.search.tavily_search_raw`` but typed for clarity inside v4."""

    url: str
    title: str
    snippet: str
    published_date: str = ""


class Finding(BaseModel):
    """One factual claim about the rep, with the source URLs that support it.

    Produced by the research_agent (from filtered breadth results) and
    by depth subagents (from focused per-topic searches). Consumed by
    the formatter, which renders bullets and assembles the unified
    citation list from ``source_urls``.
    """

    claim: str = Field(description="One-sentence factual statement.")
    source_urls: list[str] = Field(
        default_factory=list,
        description="URLs from the search pool that support this claim.",
    )
    topic: str = Field(
        default="",
        description="Rough category, e.g. 'policy', 'record', 'controversy'.",
    )


class ResearchSummary(BaseModel):
    """v4's user-facing output. Same shape as v2/v3."""

    bullets: BulletList = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


__all__ = ["Citation", "Finding", "ResearchSummary", "SearchResult"]
```

- [ ] **Step 2: Verify it imports and instantiates cleanly**

```bash
cd /Users/andrewbarry/projects/my-representatives/backend && conda run -n my-reps python -c "
from research.overview.v4.models import Finding, ResearchSummary, SearchResult
f = Finding(claim='x', source_urls=['https://a.com'], topic='policy')
s = ResearchSummary()
sr = SearchResult(url='https://a.com', title='t', snippet='snip')
print(f.model_dump(), s.model_dump(), sr.model_dump())
"
```

Expected: three model dumps printed; no errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/andrewbarry/projects/my-representatives
git add backend/research/overview/v4/models.py
git commit -m "v4: define Finding, SearchResult, ResearchSummary"
```

---

## Task 3: Define LangGraph state schemas

**Files:**
- Create: `backend/research/overview/v4/state.py`

Three TypedDicts, one per scope: `V4State` (whole pipeline), `ResearchAgentState` (research_agent subgraph), `DepthState` (depth subagent). Each subgraph runs against its own state — the parent never sees the child's `messages`.

- [ ] **Step 1: Write `state.py`**

Write to `backend/research/overview/v4/state.py`:

```python
"""LangGraph state schemas for v4.

Three TypedDicts, one per scope. State isolation across subgraph
boundaries is the architectural argument for v4: a depth subagent's
``messages`` history (potentially N tool results) lives and dies in
``DepthState`` and never propagates to ``V4State`` — only structured
``findings`` cross the boundary.

Reducers (``Annotated[..., operator.add]`` and ``add_messages``) are
required only on fields that receive concurrent writes from parallel
branches.
"""

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from models import Representative
from research.overview.v4.models import Finding, ResearchSummary, SearchResult


class V4State(TypedDict, total=False):
    """Top-level pipeline state."""

    rep: Representative
    queries: list[str]
    raw_results: Annotated[list[SearchResult], operator.add]   # parallel-merge
    filtered_results: list[SearchResult]
    findings: list[Finding]
    summary: ResearchSummary | None


class ResearchAgentState(TypedDict, total=False):
    """Inner state for the research_agent subgraph.

    ``filtered_results`` and ``rep`` are passed in by the wrapper.
    ``messages`` is the agent's ReAct conversation; it is NOT lifted to
    ``V4State``. ``depth_findings`` accumulates structured findings from
    each ``request_depth_research`` tool call (via ``Command(update=...)``).
    ``findings`` is the final structured output emitted by the
    ``finalize`` node — this is what crosses back to ``V4State``.
    """

    rep: Representative
    filtered_results: list[SearchResult]
    messages: Annotated[list[BaseMessage], add_messages]
    depth_findings: Annotated[list[Finding], operator.add]
    findings: list[Finding]


class DepthState(TypedDict, total=False):
    """Inner state for one depth subagent run.

    Receives only ``rep``, ``topic``, ``reason``. Returns only
    ``findings``. Its ``messages`` history (Tavily search results, agent
    reasoning) never leaves this scope.
    """

    rep: Representative
    topic: str
    reason: str
    messages: Annotated[list[BaseMessage], add_messages]
    findings: list[Finding]


__all__ = ["DepthState", "ResearchAgentState", "V4State"]
```

- [ ] **Step 2: Verify it imports**

```bash
cd /Users/andrewbarry/projects/my-representatives/backend && conda run -n my-reps python -c "
from research.overview.v4.state import V4State, ResearchAgentState, DepthState
print('ok', V4State.__annotations__.keys(), ResearchAgentState.__annotations__.keys(), DepthState.__annotations__.keys())
"
```

Expected: `ok dict_keys([...]) dict_keys([...]) dict_keys([...])` — listing each schema's fields.

- [ ] **Step 3: Commit**

```bash
cd /Users/andrewbarry/projects/my-representatives
git add backend/research/overview/v4/state.py
git commit -m "v4: define V4State, ResearchAgentState, DepthState"
```

---

## Task 4: Write all four prompt files

**Files:**
- Create: `backend/research/overview/v4/prompts/query_gen_system.txt`
- Create: `backend/research/overview/v4/prompts/query_gen_user.txt`
- Create: `backend/research/overview/v4/prompts/research_agent_system.txt`
- Create: `backend/research/overview/v4/prompts/research_agent_user.txt`
- Create: `backend/research/overview/v4/prompts/depth_agent_system.txt`
- Create: `backend/research/overview/v4/prompts/depth_agent_user.txt`
- Create: `backend/research/overview/v4/prompts/formatter_system.txt`
- Create: `backend/research/overview/v4/prompts/formatter_user.txt`

Templates use Python `string.Template` syntax (`$variable`), matching v3.

- [ ] **Step 1: Write `query_gen_system.txt`**

Write to `backend/research/overview/v4/prompts/query_gen_system.txt`:

```
You generate a diverse, high-coverage list of web search queries to research an elected official for a voter-facing overview.

Today's date is ${current_date}.

## Coverage angles to hit (aim to cover all relevant ones)

- Policy positions and stated beliefs
- Recent votes and legislation sponsored/co-sponsored
- Notable accomplishments and signed bills
- Controversies, ethics complaints, lawsuits, scandals
- Top donors and campaign finance
- Public statements and press coverage from reputable outlets
- Local/regional news about the official
- Biographical background relevant to their current office
- Current candidacy status (running for re-election, retiring, seeking higher office)
- Pending litigation, ongoing investigations, breaking news

## Rules

- Produce exactly $num_queries queries.
- Each query is a single search string (no boolean operators, no quotes around the whole thing).
- Queries should be diverse — do NOT produce rephrasings of the same question.
- Prefer queries that name the official explicitly and include specific angles (e.g. "Senator Jane Smith 2024 infrastructure vote" not "Jane Smith stuff").
- Include at least one query that targets recent controversies and at least one that targets campaign donors.
- Include at least one query targeting current/breaking news with the current year.
- Do NOT add a query that asks for a summary or biography of the official as a whole — the downstream step distills from your results. Your queries should retrieve specifics.
```

- [ ] **Step 2: Write `query_gen_user.txt`**

Write to `backend/research/overview/v4/prompts/query_gen_user.txt`:

```
Generate exactly $num_queries diverse search queries to research $name, who serves as $office. Output a list of strings in the ``queries`` field of your structured output, nothing else.
```

- [ ] **Step 3: Write `research_agent_system.txt`**

Write to `backend/research/overview/v4/prompts/research_agent_system.txt`:

```
You are a nonpartisan political research agent. You will be given pre-fetched web search results about an elected official. Your job: extract concise factual findings and decide whether any need a focused depth-research refresh before the pipeline finalizes.

Today's date is ${current_date}.

## What you have access to

- The pre-filtered search results inline in the user message: each numbered, with title, URL, snippet, and (sometimes) published date.
- One tool: ``request_depth_research(topic, reason)``.

## When to call ``request_depth_research``

ONLY for claims where staleness genuinely matters and the breadth snippets might be out of date:

- Ongoing controversies, scandals, ethics complaints
- Pending litigation or investigations
- Candidacy status (running, withdrawing, seeking higher office)
- Breaking or developing news

DO NOT call it for stable facts (biography, voting record from prior years, long-held policy positions).

## Hard limits

- Maximum $max_depth_calls depth-research calls per run, total. Budget them.
- If you have called depth research $max_depth_calls times, stop calling it and respond with a final message instead.

## When you're done

Once you are satisfied that you have the information needed (and have used your depth-research budget appropriately or chosen not to use it), respond with a regular message — NOT a tool call. The pipeline's ``finalize`` step will read your conversation and the depth-research findings to extract structured ``Finding`` objects, so your final message can simply acknowledge completion. The ``finalize`` step does the actual extraction; do not attempt to extract findings yourself in prose.
```

- [ ] **Step 4: Write `research_agent_user.txt`**

Write to `backend/research/overview/v4/prompts/research_agent_user.txt`:

```
Official: $name
Office: $office

Pre-filtered search results (cite URLs from this list when relevant):

$results_block

---

Review these results. Identify any claims that look potentially stale and where freshness matters per your instructions, and call ``request_depth_research`` for those (up to $max_depth_calls calls total). When you have used your budget appropriately or determined no depth research is needed, respond with a brief message indicating you are done — the ``finalize`` step will then extract structured findings from the breadth results and any depth findings.
```

- [ ] **Step 5: Write `depth_agent_system.txt`**

Write to `backend/research/overview/v4/prompts/depth_agent_system.txt`:

```
You are a focused research agent investigating one specific subtopic about an elected official.

Today's date is ${current_date}.

## Your job

You have one tool: ``web_search(query)``. Use it to find up-to-date information on the assigned topic. Prefer recent sources — favor results published within the last 12 months when available.

## When you're done

Once you have enough information, respond with a regular message — NOT a tool call. The pipeline will then extract structured findings from your conversation. Your prose response can be terse; the extraction step does the structured work. Do not fabricate findings; only report what your searches surfaced.

## Limits

- Cap yourself at 4 search calls. Diminishing returns set in fast at this depth.
- If two results conflict, prefer the more recent one.
```

- [ ] **Step 6: Write `depth_agent_user.txt`**

Write to `backend/research/overview/v4/prompts/depth_agent_user.txt`:

```
Official: $name
Office: $office

Topic to investigate: $topic
Why depth was requested: $reason

Use ``web_search`` to find current information on this specific topic. When done, respond with a brief message indicating completion.
```

- [ ] **Step 7: Write `formatter_system.txt`**

Write to `backend/research/overview/v4/prompts/formatter_system.txt`:

```
You are a nonpartisan political research formatter. You will receive a structured list of factual findings about an elected official, each with one or more source URLs. Your job: produce a tight, voter-useful set of bullets.

Today's date is ${current_date}.

## Output requirements

- Produce exactly 5–8 bullets total. Fewer is better than padding.
- Each bullet is a single one-liner (~15–30 words).
- Bullets blend across topics (policy, votes, controversies, donors, etc.) and are ordered by significance to a voter.
- Use the format `**3-6 word headline** - one short sentence of detail [N].` where `[N]` is one or more citation markers.
- Every factual claim must carry at least one `[N]` citation marker.

## Citations

- The user message will give you a numbered URL list — these are the ONLY URLs you may cite. You output the inline `[N]` markers; you do NOT output the citation list itself (the system will assemble it).
- Use the numbers exactly as shown in the user message.
- If a single fact is supported by multiple sources, you may cite several like `[1][3]`.

## Strict rules

- If two findings conflict, prefer the better-sourced or more recent claim.
- Omit anything weakly supported. A shorter overview beats a padded one.
- Present facts neutrally. No editorializing.
- Do not output a heading, intro line, or summary paragraph — output the bullets only (in the ``bullets`` field).
```

- [ ] **Step 8: Write `formatter_user.txt`**

Write to `backend/research/overview/v4/prompts/formatter_user.txt`:

```
Official: $name
Office: $office

Findings (each numbered; cite by the [N] of the URL list below, not these):

$findings_block

Numbered URL list (use these N values for ``[N]`` markers in your bullets):

$citations_block

---

Produce 5–8 blended bullets per the system instructions. Populate ONLY the ``bullets`` field of your structured output. Do not output a citation list.
```

- [ ] **Step 9: Verify all eight files exist and are non-empty**

```bash
ls -la /Users/andrewbarry/projects/my-representatives/backend/research/overview/v4/prompts/ && wc -l /Users/andrewbarry/projects/my-representatives/backend/research/overview/v4/prompts/*.txt
```

Expected: 8 `.txt` files listed, each with line count > 0.

- [ ] **Step 10: Commit**

```bash
cd /Users/andrewbarry/projects/my-representatives
git add backend/research/overview/v4/prompts/
git commit -m "v4: add prompt files for query gen, research agent, depth agent, formatter"
```

---

## Task 5: Implement breadth_search node

**Files:**
- Create: `backend/research/overview/v4/nodes/breadth_search.py`

Pure async function: read `state["queries"]`, run them in parallel against Tavily (bounded), return `{"raw_results": [SearchResult, ...]}`. No LLM. Reuses `tavily_search_raw` from `research/search.py`.

- [ ] **Step 1: Write `breadth_search.py`**

Write to `backend/research/overview/v4/nodes/breadth_search.py`:

```python
"""Breadth-search node — parallel Tavily fan-out, no LLM in the loop."""

import asyncio
import logging
import os

from research.overview.v4.models import SearchResult
from research.overview.v4.state import V4State
from research.search import tavily_search_raw

logger = logging.getLogger(__name__)

_RESULTS_PER_QUERY = int(os.getenv("OVERVIEW_V4_RESULTS_PER_QUERY", "5"))
_SEARCH_CONCURRENCY = int(os.getenv("OVERVIEW_V4_SEARCH_CONCURRENCY", "5"))


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
```

- [ ] **Step 2: Smoke test the import**

```bash
cd /Users/andrewbarry/projects/my-representatives/backend && conda run -n my-reps python -c "
from research.overview.v4.nodes.breadth_search import breadth_search
print('ok', breadth_search.__name__)
"
```

Expected: `ok breadth_search`

- [ ] **Step 3: Commit**

```bash
cd /Users/andrewbarry/projects/my-representatives
git add backend/research/overview/v4/nodes/breadth_search.py
git commit -m "v4: add breadth_search node (parallel Tavily, no LLM)"
```

---

## Task 6: Implement filter node

**Files:**
- Create: `backend/research/overview/v4/nodes/filter_node.py`

Pure heuristic: dedupe by URL, truncate snippet, cap total. Module is named `filter_node` (not `filter`) to avoid shadowing the builtin.

- [ ] **Step 1: Write `filter_node.py`**

Write to `backend/research/overview/v4/nodes/filter_node.py`:

```python
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
```

- [ ] **Step 2: Smoke test (run filter against constructed input)**

```bash
cd /Users/andrewbarry/projects/my-representatives/backend && conda run -n my-reps python -c "
import asyncio
from research.overview.v4.models import SearchResult
from research.overview.v4.nodes.filter_node import filter_node

raw = [
    SearchResult(url='https://a.com', title='A', snippet='x' * 1000),
    SearchResult(url='https://a.com', title='dup', snippet='dup'),
    SearchResult(url='https://b.com', title='B', snippet='b'),
    SearchResult(url='', title='empty url', snippet='-'),
]
out = asyncio.run(filter_node({'raw_results': raw}))
assert len(out['filtered_results']) == 2, out
assert len(out['filtered_results'][0].snippet) == 800
print('ok')
"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
cd /Users/andrewbarry/projects/my-representatives
git add backend/research/overview/v4/nodes/filter_node.py
git commit -m "v4: add filter node (heuristic dedupe/truncate/cap)"
```

---

## Task 7: Implement query_generator node

**Files:**
- Create: `backend/research/overview/v4/nodes/query_generator.py`

One LLM call with `with_structured_output`. Wraps a `_QueryList` Pydantic model. Adds Langfuse `@observe` and a `UsageTracker` callback. Reads the prompt templates and substitutes via `string.Template`.

The `UsageTracker` is per-node-call; the pipeline-level entrypoint will pass a shared `UsageTracker` through `state` (added in a later task). For now, this node creates its own and returns it via state under a key the entrypoint will read at the end.

**However**, returning a callback through state is awkward. The cleaner approach (and what we use here): each node creates its own `UsageTracker`, the node returns its `UsageStats` snapshot via the state, and the pipeline accumulates stats at the end. To do this, we add a `usage` field to `V4State`.

- [ ] **Step 1: Add `usage` field to `V4State`**

Edit `backend/research/overview/v4/state.py`. Find `class V4State(TypedDict, total=False):` and update it:

Old:

```python
class V4State(TypedDict, total=False):
    """Top-level pipeline state."""

    rep: Representative
    queries: list[str]
    raw_results: Annotated[list[SearchResult], operator.add]   # parallel-merge
    filtered_results: list[SearchResult]
    findings: list[Finding]
    summary: ResearchSummary | None
```

New:

```python
class V4State(TypedDict, total=False):
    """Top-level pipeline state."""

    rep: Representative
    queries: list[str]
    raw_results: Annotated[list[SearchResult], operator.add]   # parallel-merge
    filtered_results: list[SearchResult]
    findings: list[Finding]
    summary: ResearchSummary | None
    # Aggregated LLM/tool usage. Each node that does LLM work appends a
    # ``UsageStats`` to this list; the pipeline entrypoint sums them.
    usage_log: Annotated[list["UsageStats"], operator.add]
```

Add the import at the top of the file:

Old (top of file):

```python
import operator
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from models import Representative
from research.overview.v4.models import Finding, ResearchSummary, SearchResult
```

New:

```python
import operator
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from models import Representative
from research.overview.v4.models import Finding, ResearchSummary, SearchResult
from research.usage import UsageStats
```

- [ ] **Step 2: Write `query_generator.py`**

Write to `backend/research/overview/v4/nodes/query_generator.py`:

```python
"""Query generator node — single LLM call producing breadth-first search queries."""

import logging
import os
from datetime import date
from pathlib import Path
from string import Template

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langfuse import observe
from langfuse.langchain import CallbackHandler
from pydantic import BaseModel, Field

from research.overview.v4.state import V4State
from research.usage import UsageTracker

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_NUM_QUERIES = int(os.getenv("OVERVIEW_V4_NUM_QUERIES", "18"))


class _QueryList(BaseModel):
    queries: list[str] = Field(description="Diverse search queries, one per item.")


@observe(name="v4-query-gen")
async def query_generator(state: V4State) -> dict:
    """Single LLM call (no tools) that emits ``_NUM_QUERIES`` diverse queries."""
    rep = state["rep"]
    langfuse_handler = CallbackHandler()
    usage_tracker = UsageTracker()

    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    )
    structured = model.with_structured_output(_QueryList)

    system_template = Template((_PROMPTS_DIR / "query_gen_system.txt").read_text())
    user_template = Template((_PROMPTS_DIR / "query_gen_user.txt").read_text())
    system_prompt = system_template.substitute(
        current_date=date.today().isoformat(), num_queries=str(_NUM_QUERIES)
    )
    user_prompt = user_template.substitute(
        name=rep.name, office=rep.office, num_queries=str(_NUM_QUERIES)
    )

    result = await structured.ainvoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
        config={
            "callbacks": [langfuse_handler, usage_tracker],
            "run_name": f"v4:query-gen:{rep.name}",
        },
    )
    queries = [q.strip() for q in result.queries if q and q.strip()]
    logger.info(f"[v4] Generated {len(queries)} queries for {rep.name}")
    return {"queries": queries, "usage_log": [usage_tracker.stats]}
```

- [ ] **Step 3: Smoke test the import + (no live LLM call)**

```bash
cd /Users/andrewbarry/projects/my-representatives/backend && conda run -n my-reps python -c "
from research.overview.v4.nodes.query_generator import query_generator, _QueryList
print('ok', query_generator.__name__, _QueryList.model_fields.keys())
"
```

Expected: `ok query_generator dict_keys(['queries'])`

- [ ] **Step 4: Commit**

```bash
cd /Users/andrewbarry/projects/my-representatives
git add backend/research/overview/v4/state.py backend/research/overview/v4/nodes/query_generator.py
git commit -m "v4: add query_generator node + usage_log state field"
```

---

## Task 8: Implement Tavily search tool wrapper for the depth subagent

**Files:**
- Create: `backend/research/overview/v4/tools/tavily_search.py`

The depth subagent needs a LangChain `@tool` to bind to its LLM. We can't reuse `research.search.web_search` directly because it's a global module-level tool — but its formatting is exactly what we need. We re-export it for clarity, importing from the existing module so behavior stays identical.

- [ ] **Step 1: Write `tavily_search.py`**

Write to `backend/research/overview/v4/tools/tavily_search.py`:

```python
"""LangChain ``@tool`` for the depth subagent's web search.

Re-exports ``research.search.web_search`` unchanged. v4 keeps the import
local so the depth subgraph reads as self-contained and so we can swap in
a v4-specific variant later without touching shared code.
"""

from research.search import web_search

depth_web_search = web_search

__all__ = ["depth_web_search"]
```

- [ ] **Step 2: Smoke test the import**

```bash
cd /Users/andrewbarry/projects/my-representatives/backend && conda run -n my-reps python -c "
from research.overview.v4.tools.tavily_search import depth_web_search
print('ok', depth_web_search.name)
"
```

Expected: `ok web_search`

- [ ] **Step 3: Commit**

```bash
cd /Users/andrewbarry/projects/my-representatives
git add backend/research/overview/v4/tools/tavily_search.py
git commit -m "v4: add depth_web_search tool wrapper"
```

---

## Task 9: Implement depth_subgraph

**Files:**
- Create: `backend/research/overview/v4/nodes/depth_subgraph.py`

This is the first real LangGraph subgraph. Three nodes: `agent` (LLM with `depth_web_search`), `tools` (`ToolNode`), `finalize` (extracts structured `Finding` list from the agent's messages via `with_structured_output`). Conditional edge after `agent`: tool calls → `tools`; no tool calls → `finalize`.

- [ ] **Step 1: Write `depth_subgraph.py`**

Write to `backend/research/overview/v4/nodes/depth_subgraph.py`:

```python
"""Depth subgraph — focused per-topic ReAct subagent with isolated state.

State (DepthState) is fully isolated from the parent. The subagent's
``messages`` (Tavily search results, agent reasoning) live and die in
this scope. Only the structured ``findings`` list crosses back to the
caller (the ``request_depth_research`` tool).
"""

import logging
import os
from datetime import date
from pathlib import Path
from string import Template

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from research.overview.v4.models import Finding
from research.overview.v4.state import DepthState
from research.overview.v4.tools.tavily_search import depth_web_search

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_DEPTH_RECURSION_LIMIT = int(os.getenv("OVERVIEW_V4_DEPTH_RECURSION_LIMIT", "8"))


class _FindingsList(BaseModel):
    """LLM-facing schema used by the depth subagent's finalize node."""

    findings: list[Finding] = Field(default_factory=list)


def _build_initial_messages(state: DepthState) -> list:
    system_template = Template((_PROMPTS_DIR / "depth_agent_system.txt").read_text())
    user_template = Template((_PROMPTS_DIR / "depth_agent_user.txt").read_text())
    system_prompt = system_template.substitute(current_date=date.today().isoformat())
    user_prompt = user_template.substitute(
        name=state["rep"].name,
        office=state["rep"].office,
        topic=state["topic"],
        reason=state["reason"],
    )
    return [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]


async def _agent_node(state: DepthState) -> dict:
    """LLM node: bound to depth_web_search tool. Adds initial system+user
    messages on the first turn (when ``messages`` is empty) so callers
    don't need to construct them."""
    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    ).bind_tools([depth_web_search])

    messages = state.get("messages") or []
    if not messages:
        messages = _build_initial_messages(state)
    response = await model.ainvoke(messages)
    # If we seeded the initial messages, return them along with the
    # response so add_messages picks them up into state.
    if not state.get("messages"):
        return {"messages": messages + [response]}
    return {"messages": [response]}


def _route_after_agent(state: DepthState) -> str:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return "finalize"


async def _finalize_node(state: DepthState) -> dict:
    """Extract a structured ``list[Finding]`` from the depth conversation.

    Uses a fresh model instance with ``with_structured_output`` — the
    extractor sees the full message history and emits ``Finding`` objects.
    """
    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    ).with_structured_output(_FindingsList)

    extraction_prompt = SystemMessage(
        content=(
            f"You are extracting structured findings from a depth-research "
            f"conversation about an elected official, focused on the topic: "
            f"{state['topic']!r}. Read the conversation that follows and emit "
            "a list of Finding objects (claim, source_urls, topic). The "
            "``topic`` field on every Finding should be set to "
            f"{state['topic']!r}. Cite only URLs that appeared in the "
            "search results. If the conversation surfaced no usable claims, "
            "return an empty findings list."
        )
    )
    result = await model.ainvoke([extraction_prompt, *state["messages"]])
    findings = [
        Finding(claim=f.claim, source_urls=f.source_urls, topic=state["topic"])
        for f in result.findings
    ]
    logger.info(
        f"[v4] Depth subagent finalize for topic={state['topic']!r}: "
        f"{len(findings)} findings"
    )
    return {"findings": findings}


def build_depth_graph():
    g = StateGraph(DepthState)
    g.add_node("agent", _agent_node)
    g.add_node("tools", ToolNode([depth_web_search]))
    g.add_node("finalize", _finalize_node)
    g.add_edge(START, "agent")
    g.add_conditional_edges(
        "agent",
        _route_after_agent,
        {"tools": "tools", "finalize": "finalize"},
    )
    g.add_edge("tools", "agent")
    g.add_edge("finalize", END)
    return g.compile()


# Module-level compiled subgraph. Reused across all depth tool calls
# in a pipeline run; LangGraph compiled graphs are stateless.
depth_graph = build_depth_graph()

# Re-export for callers/tests.
DEPTH_RECURSION_LIMIT = _DEPTH_RECURSION_LIMIT


__all__ = ["DEPTH_RECURSION_LIMIT", "build_depth_graph", "depth_graph"]
```

- [ ] **Step 2: Smoke test that the graph compiles**

```bash
cd /Users/andrewbarry/projects/my-representatives/backend && conda run -n my-reps python -c "
from research.overview.v4.nodes.depth_subgraph import depth_graph, DEPTH_RECURSION_LIMIT
print('ok', type(depth_graph).__name__, 'limit=', DEPTH_RECURSION_LIMIT)
"
```

Expected: `ok CompiledStateGraph limit= 8` (class name may vary slightly across LangGraph versions; just check it compiles).

- [ ] **Step 3: Commit**

```bash
cd /Users/andrewbarry/projects/my-representatives
git add backend/research/overview/v4/nodes/depth_subgraph.py
git commit -m "v4: add depth subgraph (per-topic ReAct subagent w/ isolated state)"
```

---

## Task 10: Implement request_depth_research tool

**Files:**
- Create: `backend/research/overview/v4/tools/request_depth.py`

The bridge between `research_agent` and `depth_subgraph`. The tool is a closure factory: given a `rep`, it returns a `@tool`-decorated callable bound to the LLM. When called, the tool builds a fresh `DepthState`, invokes the compiled `depth_graph`, and returns a `Command(update=...)` to mutate the parent (research_agent) state with new findings. The `Command` also carries the `ToolMessage` so the agent's conversation reflects the tool result.

- [ ] **Step 1: Write `request_depth.py`**

Write to `backend/research/overview/v4/tools/request_depth.py`:

```python
"""``request_depth_research`` tool factory — the bridge between
research_agent and depth_subgraph.

Returns a ``Command(update=...)`` so depth findings are written
directly into the parent research_agent's state via LangGraph's
state-from-tool pattern. The tool ALSO returns a ``ToolMessage``
(carried inside the Command) so the agent sees a conversational
acknowledgement of its tool call.
"""

import logging
from typing import Annotated, Callable

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.types import Command

from models import Representative
from research.overview.v4.nodes.depth_subgraph import (
    DEPTH_RECURSION_LIMIT,
    depth_graph,
)

logger = logging.getLogger(__name__)


def _format_findings_for_agent(findings: list, topic: str) -> str:
    if not findings:
        return f"Depth research on '{topic}' returned no usable findings."
    lines = [f"Depth research on '{topic}' — {len(findings)} finding(s):"]
    for i, f in enumerate(findings, start=1):
        urls = ", ".join(f.source_urls[:3])
        lines.append(f"  {i}. {f.claim} (sources: {urls})")
    return "\n".join(lines)


def make_request_depth_tool(rep: Representative) -> Callable:
    """Build the depth-research tool bound to this pipeline run's rep.

    The tool is constructed per-pipeline-run so ``rep`` is captured via
    closure and never exposed to the LLM.
    """

    @tool
    async def request_depth_research(
        topic: str,
        reason: str,
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        """Run a focused depth investigation on a specific subtopic. Use only
        for volatile/time-sensitive claims (ongoing controversies, pending
        litigation, candidacy status, breaking news). Argument ``topic`` is
        the subject to investigate; ``reason`` briefly explains why depth
        is needed."""
        logger.info(f"[v4] Depth research requested for topic={topic!r} reason={reason!r}")
        try:
            result = await depth_graph.ainvoke(
                {
                    "rep": rep,
                    "topic": topic,
                    "reason": reason,
                    "messages": [],
                    "findings": [],
                },
                config={"recursion_limit": DEPTH_RECURSION_LIMIT},
            )
        except Exception as e:
            logger.error(f"[v4] Depth subgraph failed for topic={topic!r}: {e}", exc_info=True)
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=f"Depth research on '{topic}' failed: {e}",
                            tool_call_id=tool_call_id,
                        )
                    ]
                }
            )

        findings = result.get("findings", [])
        summary = _format_findings_for_agent(findings, topic)
        return Command(
            update={
                "depth_findings": findings,
                "messages": [
                    ToolMessage(content=summary, tool_call_id=tool_call_id)
                ],
            }
        )

    return request_depth_research


__all__ = ["make_request_depth_tool"]
```

- [ ] **Step 2: Smoke test that the factory produces a tool**

```bash
cd /Users/andrewbarry/projects/my-representatives/backend && conda run -n my-reps python -c "
from models import Representative, Contact
from research.overview.v4.tools.request_depth import make_request_depth_tool
rep = Representative(name='Test', office='Senator', level='federal')
t = make_request_depth_tool(rep)
print('ok', t.name, t.description[:60])
"
```

Expected: `ok request_depth_research Run a focused depth investigation...`

- [ ] **Step 3: Commit**

```bash
cd /Users/andrewbarry/projects/my-representatives
git add backend/research/overview/v4/tools/request_depth.py
git commit -m "v4: add request_depth_research tool factory (Command-based state update)"
```

---

## Task 11: Implement research_agent subgraph

**Files:**
- Create: `backend/research/overview/v4/nodes/research_agent.py`

Same three-node pattern as the depth subgraph (`agent` → conditional → `tools` or `finalize`), but:
- The bound tool is `request_depth_research` (factory-built per run).
- The initial human message includes the formatted breadth `filtered_results` block.
- The `finalize` node extracts findings from filtered_results + accumulated `depth_findings` (depth findings are authoritative for their topics; finalize prefers them over breadth claims on overlapping topics).

The wrapper node `research_agent_node(state: V4State) -> dict` invokes the compiled subgraph and returns ONLY `{"findings": ...}` plus accumulated usage to the parent state — bridging the boundary.

- [ ] **Step 1: Write `research_agent.py`**

Write to `backend/research/overview/v4/nodes/research_agent.py`:

```python
"""Research-agent subgraph + V4State wrapper node.

Subgraph topology:
  agent ──tool_calls──▶ tools ──▶ agent
  agent ──no calls──▶ finalize ──▶ END

State boundary: only ``findings`` (the structured output of finalize)
crosses back to V4State. The agent's ``messages`` history and
``depth_findings`` accumulator stay inside ResearchAgentState.
"""

import logging
import os
from datetime import date
from pathlib import Path
from string import Template

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langfuse import observe
from langfuse.langchain import CallbackHandler
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from research.overview.v4.models import Finding, SearchResult
from research.overview.v4.state import ResearchAgentState, V4State
from research.overview.v4.tools.request_depth import make_request_depth_tool
from research.usage import UsageTracker

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_AGENT_RECURSION_LIMIT = 12
_MAX_DEPTH_CALLS = int(os.getenv("OVERVIEW_V4_AGENT_MAX_DEPTH_CALLS", "3"))


class _FindingsList(BaseModel):
    findings: list[Finding] = Field(default_factory=list)


def _format_results_block(results: list[SearchResult]) -> str:
    if not results:
        return "(no results)"
    lines = []
    for i, r in enumerate(results, start=1):
        date_suffix = f"  Published: {r.published_date}\n" if r.published_date else ""
        lines.append(
            f"[{i}] {r.title}\n  URL: {r.url}\n{date_suffix}  {r.snippet}"
        )
    return "\n\n".join(lines)


def _build_initial_messages(state: ResearchAgentState) -> list:
    system_template = Template((_PROMPTS_DIR / "research_agent_system.txt").read_text())
    user_template = Template((_PROMPTS_DIR / "research_agent_user.txt").read_text())
    system_prompt = system_template.substitute(
        current_date=date.today().isoformat(),
        max_depth_calls=str(_MAX_DEPTH_CALLS),
    )
    user_prompt = user_template.substitute(
        name=state["rep"].name,
        office=state["rep"].office,
        results_block=_format_results_block(state["filtered_results"]),
        max_depth_calls=str(_MAX_DEPTH_CALLS),
    )
    return [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]


def build_research_agent_graph(request_depth_tool):
    """Build (and compile) a research_agent subgraph bound to ``request_depth_tool``.

    The tool is rep-specific (closure-bound), so the graph is built per
    pipeline run.
    """

    async def _agent_node(state: ResearchAgentState) -> dict:
        model = ChatAnthropic(
            model=os.environ["CLAUDE_MODEL"],
            max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
        ).bind_tools([request_depth_tool])

        messages = state.get("messages") or []
        if not messages:
            messages = _build_initial_messages(state)
        response = await model.ainvoke(messages)
        if not state.get("messages"):
            return {"messages": messages + [response]}
        return {"messages": [response]}

    def _route_after_agent(state: ResearchAgentState) -> str:
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        return "finalize"

    async def _finalize_node(state: ResearchAgentState) -> dict:
        """Extract structured findings from filtered_results + depth_findings.

        Depth findings carry authoritative-fresh information for their
        topics; the extractor is told to prefer them on overlap.
        """
        model = ChatAnthropic(
            model=os.environ["CLAUDE_MODEL"],
            max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
        ).with_structured_output(_FindingsList)

        depth = state.get("depth_findings") or []
        depth_block = "(none)"
        if depth:
            lines = []
            for f in depth:
                urls = ", ".join(f.source_urls[:3])
                lines.append(
                    f"- topic={f.topic!r}: {f.claim} (sources: {urls})"
                )
            depth_block = "\n".join(lines)

        extraction_prompt = SystemMessage(
            content=(
                "You are extracting structured Finding objects from research "
                "material about an elected official. For every Finding: "
                "claim is one factual sentence; source_urls lists URLs from "
                "the materials below; topic is a short category like "
                "'policy', 'record', 'controversy', 'donors', 'candidacy'.\n\n"
                "When the breadth results and depth findings overlap on a "
                "topic, the DEPTH FINDINGS are authoritative-fresh — prefer "
                "them and discard stale breadth claims on that topic.\n\n"
                "Cite only URLs that actually appear in the materials. "
                "Aim for 8–14 findings total (fewer is fine if breadth is "
                "thin). Do not invent claims."
            )
        )

        materials = HumanMessage(
            content=(
                f"Official: {state['rep'].name}\n"
                f"Office: {state['rep'].office}\n\n"
                f"Pre-filtered breadth search results:\n\n"
                f"{_format_results_block(state['filtered_results'])}\n\n"
                f"---\n\nDepth-research findings (authoritative-fresh):\n\n"
                f"{depth_block}\n\n"
                f"---\n\nExtract Findings now."
            )
        )

        result = await model.ainvoke([extraction_prompt, materials])
        logger.info(
            f"[v4] research_agent finalize for {state['rep'].name}: "
            f"{len(result.findings)} findings (depth contributed "
            f"{len(depth)})"
        )
        return {"findings": result.findings}

    g = StateGraph(ResearchAgentState)
    g.add_node("agent", _agent_node)
    g.add_node("tools", ToolNode([request_depth_tool]))
    g.add_node("finalize", _finalize_node)
    g.add_edge(START, "agent")
    g.add_conditional_edges(
        "agent",
        _route_after_agent,
        {"tools": "tools", "finalize": "finalize"},
    )
    g.add_edge("tools", "agent")
    g.add_edge("finalize", END)
    return g.compile()


@observe(name="v4-research-agent")
async def research_agent_node(state: V4State) -> dict:
    """V4State wrapper: build the per-run subgraph, invoke it, return only
    ``findings`` to V4State. The agent's messages and depth_findings
    accumulator stay inside ResearchAgentState and are dropped at the
    boundary.
    """
    rep = state["rep"]
    langfuse_handler = CallbackHandler()
    usage_tracker = UsageTracker()

    request_depth_tool = make_request_depth_tool(rep)
    agent_graph = build_research_agent_graph(request_depth_tool)

    inner: ResearchAgentState = {
        "rep": rep,
        "filtered_results": state["filtered_results"],
        "messages": [],
        "depth_findings": [],
        "findings": [],
    }
    result = await agent_graph.ainvoke(
        inner,
        config={
            "callbacks": [langfuse_handler, usage_tracker],
            "recursion_limit": _AGENT_RECURSION_LIMIT,
            "run_name": f"v4:research-agent:{rep.name}",
        },
    )
    findings = result.get("findings") or []
    logger.info(
        f"[v4] research_agent_node for {rep.name}: {len(findings)} findings, "
        f"{usage_tracker.stats.tool_calls} depth calls"
    )
    return {"findings": findings, "usage_log": [usage_tracker.stats]}


__all__ = [
    "build_research_agent_graph",
    "research_agent_node",
]
```

- [ ] **Step 2: Smoke test that the wrapper imports and the per-run build works**

```bash
cd /Users/andrewbarry/projects/my-representatives/backend && conda run -n my-reps python -c "
from models import Representative
from research.overview.v4.nodes.research_agent import build_research_agent_graph, research_agent_node
from research.overview.v4.tools.request_depth import make_request_depth_tool

rep = Representative(name='Test', office='Senator', level='federal')
tool = make_request_depth_tool(rep)
g = build_research_agent_graph(tool)
print('ok', type(g).__name__)
"
```

Expected: `ok CompiledStateGraph` (class name may vary).

- [ ] **Step 3: Commit**

```bash
cd /Users/andrewbarry/projects/my-representatives
git add backend/research/overview/v4/nodes/research_agent.py
git commit -m "v4: add research_agent subgraph + V4State wrapper node"
```

---

## Task 12: Implement formatter node

**Files:**
- Create: `backend/research/overview/v4/nodes/formatter.py`

Single LLM call. Builds unified citation list in Python from `findings[*].source_urls` (deduped, ordered, with `published_date` reattached from the prior `filtered_results` lookup). The LLM receives findings with explicit `[N]` references already mapped to citation indices and emits ONLY bullet text. Citations are NEVER round-tripped through the model.

- [ ] **Step 1: Write `formatter.py`**

Write to `backend/research/overview/v4/nodes/formatter.py`:

```python
"""Formatter node — final user-facing bullets + citation list.

Citation discipline (v2 lesson): the LLM emits ONLY ``bullets`` text
with ``[N]`` markers. The unified citation list is assembled in Python
from ``findings[*].source_urls`` so the structured output schema for the
LLM is the smallest possible shape (single ``list[str]``), which avoids
the Anthropic stringified-array bug.
"""

import logging
import os
from datetime import date
from pathlib import Path
from string import Template

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langfuse import observe
from langfuse.langchain import CallbackHandler
from pydantic import BaseModel

from models import Citation
from research.overview._bullet_coercion import BulletList
from research.overview.v4.models import Finding, ResearchSummary, SearchResult
from research.overview.v4.state import V4State
from research.usage import UsageTracker

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class _FormatterBullets(BaseModel):
    """LLM-facing schema. Single required ``BulletList`` only — no citations,
    no ``Optional``, no nullable union. This is the v2 stringify lesson
    applied: keep the schema minimal so Anthropic doesn't emit a list as
    a string."""

    bullets: BulletList


def _build_citations(
    findings: list[Finding],
    filtered: list[SearchResult],
) -> tuple[list[Citation], dict[str, int]]:
    """Build the unified citation list from findings' source_urls.

    Order = first appearance across findings. Returns the citation list
    and a ``url -> N`` map used to render the citations block in the
    prompt.
    """
    by_url: dict[str, SearchResult] = {r.url: r for r in filtered if r.url}
    seen: dict[str, int] = {}
    citations: list[Citation] = []
    for f in findings:
        for url in f.source_urls:
            if not url or url in seen:
                continue
            sr = by_url.get(url)
            title = sr.title if sr else url
            published = sr.published_date if sr and sr.published_date else None
            citations.append(Citation(title=title, url=url, published_date=published))
            seen[url] = len(citations)  # 1-indexed N
    return citations, seen


def _format_findings_block(findings: list[Finding], url_to_n: dict[str, int]) -> str:
    if not findings:
        return "(no findings)"
    lines = []
    for i, f in enumerate(findings, start=1):
        ns = sorted({url_to_n[u] for u in f.source_urls if u in url_to_n})
        marker = "".join(f"[{n}]" for n in ns) or "[?]"
        lines.append(f"{i}. ({f.topic}) {f.claim} {marker}")
    return "\n".join(lines)


def _format_citations_block(citations: list[Citation]) -> str:
    if not citations:
        return "(none)"
    lines = []
    for i, c in enumerate(citations, start=1):
        suffix = f" (Published: {c.published_date})" if c.published_date else ""
        lines.append(f"[{i}] {c.title} — {c.url}{suffix}")
    return "\n".join(lines)


@observe(name="v4-formatter")
async def formatter(state: V4State) -> dict:
    """Format findings into bullets; assemble citations in Python."""
    rep = state["rep"]
    findings = state.get("findings") or []
    filtered = state.get("filtered_results") or []

    citations, url_to_n = _build_citations(findings, filtered)
    findings_block = _format_findings_block(findings, url_to_n)
    citations_block = _format_citations_block(citations)

    langfuse_handler = CallbackHandler()
    usage_tracker = UsageTracker()
    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    )
    structured = model.with_structured_output(_FormatterBullets)

    system_template = Template((_PROMPTS_DIR / "formatter_system.txt").read_text())
    user_template = Template((_PROMPTS_DIR / "formatter_user.txt").read_text())
    system_prompt = system_template.substitute(current_date=date.today().isoformat())
    user_prompt = user_template.substitute(
        name=rep.name,
        office=rep.office,
        findings_block=findings_block,
        citations_block=citations_block,
    )

    result = await structured.ainvoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
        config={
            "callbacks": [langfuse_handler, usage_tracker],
            "run_name": f"v4:formatter:{rep.name}",
        },
    )

    summary = ResearchSummary(bullets=result.bullets, citations=citations)
    logger.info(
        f"[v4] Formatter for {rep.name}: {len(summary.bullets)} bullets / "
        f"{len(summary.citations)} citations"
    )
    return {"summary": summary, "usage_log": [usage_tracker.stats]}
```

- [ ] **Step 2: Smoke test (run citation-builder against constructed input — no LLM)**

```bash
cd /Users/andrewbarry/projects/my-representatives/backend && conda run -n my-reps python -c "
from research.overview.v4.models import Finding, SearchResult
from research.overview.v4.nodes.formatter import _build_citations, _format_findings_block

filtered = [SearchResult(url='https://a.com', title='A title', snippet='s'),
            SearchResult(url='https://b.com', title='B title', snippet='s', published_date='2024-01-01')]
findings = [Finding(claim='c1', source_urls=['https://a.com', 'https://b.com'], topic='policy'),
            Finding(claim='c2', source_urls=['https://b.com'], topic='record')]
cits, m = _build_citations(findings, filtered)
print('cits=', [(c.title, m[c.url]) for c in cits])
print('block=')
print(_format_findings_block(findings, m))
"
```

Expected (order-deterministic): `cits= [('A title', 1), ('B title', 2)]` and a findings block with `[1][2]` and `[2]` markers respectively.

- [ ] **Step 3: Commit**

```bash
cd /Users/andrewbarry/projects/my-representatives
git add backend/research/overview/v4/nodes/formatter.py
git commit -m "v4: add formatter node (bullets via LLM, citations via Python)"
```

---

## Task 13: Implement pipeline.py (graph wiring + research_representative entrypoint)

**Files:**
- Create: `backend/research/overview/v4/pipeline.py`

Top-level `StateGraph(V4State)`. Five nodes wired sequentially. `research_representative()` is the public entrypoint: accepts `(rep, store, research_id)`, invokes the compiled graph, sums the per-node `usage_log` into a single `UsageStats`, writes the final summary into the `InMemoryResearchStore`, and returns `(summary, usage_stats)`.

- [ ] **Step 1: Write `pipeline.py`**

Write to `backend/research/overview/v4/pipeline.py`:

```python
"""v4 overview pipeline — top-level StateGraph wiring + entrypoint.

Flow:
  query_generator → breadth_search → filter → research_agent → formatter

The research_agent node is itself a wrapper around a compiled subgraph
(see ``nodes/research_agent.py``). The depth subagent is invoked from
inside that subgraph via the ``request_depth_research`` tool — also a
compiled subgraph (see ``nodes/depth_subgraph.py``).
"""

import logging

from langfuse import observe
from langgraph.graph import END, START, StateGraph

from models import Representative
from research.overview.v4.models import ResearchSummary
from research.overview.v4.nodes.breadth_search import breadth_search
from research.overview.v4.nodes.filter_node import filter_node
from research.overview.v4.nodes.formatter import formatter
from research.overview.v4.nodes.query_generator import query_generator
from research.overview.v4.nodes.research_agent import research_agent_node
from research.overview.v4.state import V4State
from research.usage import UsageStats
from store.research_store import InMemoryResearchStore

logger = logging.getLogger(__name__)


def build_pipeline_graph():
    g = StateGraph(V4State)
    g.add_node("query_generator", query_generator)
    g.add_node("breadth_search", breadth_search)
    g.add_node("filter", filter_node)
    g.add_node("research_agent", research_agent_node)
    g.add_node("formatter", formatter)
    g.add_edge(START, "query_generator")
    g.add_edge("query_generator", "breadth_search")
    g.add_edge("breadth_search", "filter")
    g.add_edge("filter", "research_agent")
    g.add_edge("research_agent", "formatter")
    g.add_edge("formatter", END)
    return g.compile()


# Module-level compiled graph; LangGraph compiled graphs are stateless
# and reusable across runs.
pipeline_graph = build_pipeline_graph()


@observe(name="v4-research-pipeline")
async def research_representative(
    rep: Representative,
    store: InMemoryResearchStore | None = None,
    research_id: str | None = None,
) -> tuple[ResearchSummary | None, UsageStats]:
    """Public entrypoint matching the v1/v2/v3 contract."""
    total = UsageStats()
    logger.info(f"[v4] Starting research for {rep.name}")

    initial: V4State = {"rep": rep, "usage_log": []}
    try:
        result = await pipeline_graph.ainvoke(
            initial,
            config={"run_name": f"v4:pipeline:{rep.name}"},
        )
    except Exception as e:
        logger.error(f"[v4] Pipeline failed for {rep.name}: {e}", exc_info=True)
        return None, total

    for stats in result.get("usage_log") or []:
        total += stats

    summary = result.get("summary")
    if summary is None:
        logger.error(f"[v4] Pipeline returned no summary for {rep.name}")
        return None, total

    if store and research_id:
        # TOTAL_SECTIONS=1 — a single complete_section moves the task to "complete".
        await store.complete_section(
            research_id, "bullets", summary.bullets, summary.citations
        )

    logger.info(
        f"[v4] Research for {rep.name}: "
        f"{total.input_tokens} in / {total.output_tokens} out / "
        f"{total.tool_calls} tool calls; "
        f"{len(summary.bullets)} bullets / {len(summary.citations)} citations"
    )
    return summary, total
```

- [ ] **Step 2: Smoke test the import + graph compilation**

```bash
cd /Users/andrewbarry/projects/my-representatives/backend && conda run -n my-reps python -c "
from research.overview.v4.pipeline import pipeline_graph, research_representative
print('ok', type(pipeline_graph).__name__, research_representative.__name__)
"
```

Expected: `ok CompiledStateGraph research_representative` (class name may vary).

- [ ] **Step 3: Commit**

```bash
cd /Users/andrewbarry/projects/my-representatives
git add backend/research/overview/v4/pipeline.py
git commit -m "v4: add pipeline.py (StateGraph wiring + research_representative entrypoint)"
```

---

## Task 14: Wire v4 contract into v4/__init__.py

**Files:**
- Modify: `backend/research/overview/v4/__init__.py`

- [ ] **Step 1: Replace contents of `v4/__init__.py`**

Write to `backend/research/overview/v4/__init__.py`:

```python
"""v4 overview pipeline — LangGraph-native breadth-first + adaptive-depth.

Exports the v3-compatible contract: ``ResearchSummary``,
``research_representative``, and ``TOTAL_SECTIONS``. ``TOTAL_SECTIONS=1``
because the entire pipeline writes once to the InMemoryResearchStore at
the end (no per-section streaming).
"""

from research.overview.v4.models import ResearchSummary
from research.overview.v4.pipeline import research_representative

TOTAL_SECTIONS = 1

__all__ = ["ResearchSummary", "TOTAL_SECTIONS", "research_representative"]
```

- [ ] **Step 2: Smoke test the contract**

```bash
cd /Users/andrewbarry/projects/my-representatives/backend && conda run -n my-reps python -c "
from research.overview.v4 import ResearchSummary, TOTAL_SECTIONS, research_representative
print('ok', ResearchSummary.__name__, TOTAL_SECTIONS, research_representative.__name__)
"
```

Expected: `ok ResearchSummary 1 research_representative`

- [ ] **Step 3: Commit**

```bash
cd /Users/andrewbarry/projects/my-representatives
git add backend/research/overview/v4/__init__.py
git commit -m "v4: export ResearchSummary, research_representative, TOTAL_SECTIONS"
```

---

## Task 15: Wire v4 into the version-dispatch package

**Files:**
- Modify: `backend/research/overview/__init__.py`

Add a `v4` branch to the version dispatch alongside v1/v2/v3.

- [ ] **Step 1: Edit `research/overview/__init__.py`**

Edit `backend/research/overview/__init__.py`. Find the version-dispatch block and add a v4 branch:

Old:

```python
"""Dispatch to the active rep overview pipeline version.

Selected at import time via the ``OVERVIEW_PIPELINE_VERSION`` env var.
Supported values: ``v1`` (default), ``v2``, ``v3``.

Each version's package must export ``ResearchSummary``,
``research_representative``, and ``TOTAL_SECTIONS``.
"""

import os

ACTIVE_VERSION = os.getenv("OVERVIEW_PIPELINE_VERSION", "v1")

if ACTIVE_VERSION == "v1":
    from .v1 import ResearchSummary, TOTAL_SECTIONS, research_representative
elif ACTIVE_VERSION == "v2":
    from .v2 import ResearchSummary, TOTAL_SECTIONS, research_representative
elif ACTIVE_VERSION == "v3":
    from .v3 import ResearchSummary, TOTAL_SECTIONS, research_representative
else:
    raise ValueError(
        f"Unknown OVERVIEW_PIPELINE_VERSION: {ACTIVE_VERSION!r}. "
        "Expected one of: v1, v2, v3."
    )
```

New:

```python
"""Dispatch to the active rep overview pipeline version.

Selected at import time via the ``OVERVIEW_PIPELINE_VERSION`` env var.
Supported values: ``v1`` (default), ``v2``, ``v3``, ``v4``.

Each version's package must export ``ResearchSummary``,
``research_representative``, and ``TOTAL_SECTIONS``.
"""

import os

ACTIVE_VERSION = os.getenv("OVERVIEW_PIPELINE_VERSION", "v1")

if ACTIVE_VERSION == "v1":
    from .v1 import ResearchSummary, TOTAL_SECTIONS, research_representative
elif ACTIVE_VERSION == "v2":
    from .v2 import ResearchSummary, TOTAL_SECTIONS, research_representative
elif ACTIVE_VERSION == "v3":
    from .v3 import ResearchSummary, TOTAL_SECTIONS, research_representative
elif ACTIVE_VERSION == "v4":
    from .v4 import ResearchSummary, TOTAL_SECTIONS, research_representative
else:
    raise ValueError(
        f"Unknown OVERVIEW_PIPELINE_VERSION: {ACTIVE_VERSION!r}. "
        "Expected one of: v1, v2, v3, v4."
    )
```

- [ ] **Step 2: Smoke test that v4 dispatches correctly**

```bash
cd /Users/andrewbarry/projects/my-representatives/backend && OVERVIEW_PIPELINE_VERSION=v4 conda run -n my-reps python -c "
from research.overview import ACTIVE_VERSION, ResearchSummary, TOTAL_SECTIONS, research_representative
print('ok', ACTIVE_VERSION, TOTAL_SECTIONS, ResearchSummary.__module__)
"
```

Expected: `ok v4 1 research.overview.v4.models`

- [ ] **Step 3: Smoke test that v3 still works (no regression)**

```bash
cd /Users/andrewbarry/projects/my-representatives/backend && OVERVIEW_PIPELINE_VERSION=v3 conda run -n my-reps python -c "
from research.overview import ACTIVE_VERSION
print('ok', ACTIVE_VERSION)
"
```

Expected: `ok v3`

- [ ] **Step 4: Commit**

```bash
cd /Users/andrewbarry/projects/my-representatives
git add backend/research/overview/__init__.py
git commit -m "v4: wire into OVERVIEW_PIPELINE_VERSION dispatch"
```

---

## Task 16: End-to-end smoke test against a real rep

**Files:**
- (no new files; this is a runtime verification task)

Run the pipeline against a real rep using the running backend. This validates:
- All nodes wire together correctly
- LLM calls succeed
- Tavily fan-out works
- Depth subagent invokes when called
- Formatter produces a valid `ResearchSummary` (non-empty bullets, citations)
- Frontend dispatch still works (existing component handles bullets shape)

- [ ] **Step 1: Confirm `.env` has all required keys**

```bash
cd /Users/andrewbarry/projects/my-representatives && grep -E '^(ANTHROPIC_API_KEY|TAVILY_API_KEY|CLAUDE_MODEL|RESEARCH_MAX_TOKENS|LANGFUSE_)' .env | sed 's/=.*/=***SET***/'
```

Expected: each key listed with `=***SET***`. If any are missing, stop and ask the user to populate `.env` before continuing.

- [ ] **Step 2: Direct-invocation smoke test (no HTTP layer)**

This runs the pipeline as a script and prints the summary. Set a small query count to keep the run fast.

```bash
cd /Users/andrewbarry/projects/my-representatives/backend && \
  OVERVIEW_PIPELINE_VERSION=v4 \
  OVERVIEW_V4_NUM_QUERIES=6 \
  OVERVIEW_V4_RESULTS_PER_QUERY=3 \
  OVERVIEW_V4_AGENT_MAX_DEPTH_CALLS=1 \
  conda run -n my-reps python -c "
import asyncio, logging
logging.basicConfig(level=logging.INFO)
from dotenv import load_dotenv
load_dotenv('../.env')
from models import Representative
from research.overview.v4 import research_representative

async def main():
    rep = Representative(name='Chuck Schumer', office='U.S. Senator (NY)', level='federal')
    summary, usage = await research_representative(rep)
    print('---')
    print('USAGE:', usage)
    print('BULLETS:')
    for b in (summary.bullets if summary else []):
        print('  -', b)
    print('CITATIONS:')
    for c in (summary.citations if summary else []):
        print('  -', c.title, c.url)

asyncio.run(main())
"
```

Expected:
- `[v4]` log lines for each node
- 5–8 bullets printed under `BULLETS:`
- Several citations printed under `CITATIONS:`
- `USAGE:` shows non-zero `input_tokens`, `output_tokens`, and `tool_calls`
- A Langfuse trace appears at https://langfuse.com (or your `LANGFUSE_BASE_URL`) named `v4-research-pipeline`

If the run fails: read the error, identify which node, fix the bug in that node's file, and rerun. Common issues: env var typos, prompt template variable mismatches, depth subagent recursion limit too low.

- [ ] **Step 3: HTTP-layer smoke test via the FastAPI backend**

Run the backend with v4 selected:

```bash
cd /Users/andrewbarry/projects/my-representatives/backend && \
  OVERVIEW_PIPELINE_VERSION=v4 \
  conda run -n my-reps uvicorn main:app --reload --port 8000
```

In a second terminal, post a research request:

```bash
curl -s -X POST http://localhost:8000/api/research \
  -H 'Content-Type: application/json' \
  -d '{"representative":{"name":"Chuck Schumer","office":"U.S. Senator (NY)","level":"federal"}}'
```

Expected: `{"research_id":"<hex>","status":"pending","summary":null}` (or `"complete"` with a cached summary).

Poll the result a few times until status is `complete` (or `failed`):

```bash
curl -s http://localhost:8000/api/research/<RESEARCH_ID> | head -c 1000
```

Expected on success: `status: "complete"` and a non-empty `summary.bullets` array.

Stop the backend when done (Ctrl+C in the uvicorn terminal).

- [ ] **Step 4: Commit a NOTES file (optional, only if behavior worth recording)**

If the smoke test surfaced anything notable (latency observations, prompt tweaks, depth-call frequency), add a brief note. If everything worked cleanly, skip this step.

```bash
cd /Users/andrewbarry/projects/my-representatives
# only if you have notes to commit:
# git add <file>
# git commit -m "v4: smoke test notes"
```

---

## Task 17: Update CLAUDE.md with v4

**Files:**
- Modify: `CLAUDE.md`

Add a v4 bullet under the rep-overview-pipeline section, list the new env vars, add v4 trace names, and update `task_type` to include `rep:v4`.

- [ ] **Step 1: Add v4 to the pipeline-versions bullet list in CLAUDE.md**

Edit `/Users/andrewbarry/projects/my-representatives/CLAUDE.md`. Find the line that begins `- **v3** (\`research/overview/v3/\`)` and the paragraph that follows it. After that v3 paragraph, insert a new bullet:

Old:

```markdown
- **v3** (`research/overview/v3/`) — breadth-first retrieval: 1 LLM call generates ~15 queries, parallel Tavily fan-out (no LLM in the loop), `prefilter.py` dedupes/truncates, then one distillation call emits bullets + citations. `TOTAL_SECTIONS=1`. Prompts in `research/overview/v3/prompts/`. Tunable via `OVERVIEW_V3_*` env vars (see below). Distillation bullets *are* user-facing, so the distill prompt specifies the `**headline** - sentence [N]` display format.
```

New:

```markdown
- **v3** (`research/overview/v3/`) — breadth-first retrieval: 1 LLM call generates ~15 queries, parallel Tavily fan-out (no LLM in the loop), `prefilter.py` dedupes/truncates, then one distillation call emits bullets + citations. `TOTAL_SECTIONS=1`. Prompts in `research/overview/v3/prompts/`. Tunable via `OVERVIEW_V3_*` env vars (see below). Distillation bullets *are* user-facing, so the distill prompt specifies the `**headline** - sentence [N]` display format.
- **v4** (`research/overview/v4/`) — LangGraph-native breadth + adaptive depth. A top-level `StateGraph(V4State)` wires `query_generator → breadth_search → filter → research_agent → formatter`. The research_agent is a compiled subgraph with one tool, `request_depth_research`, which itself invokes a second compiled subgraph (`depth_subgraph`) under an isolated `DepthState`. State isolation across subgraph boundaries prevents the token-accumulation problem v1/v2 suffered: a depth subagent's tool-call history (Tavily snippets, agent reasoning) lives and dies in `DepthState` — only structured `Finding` objects cross back to the research_agent, and only `findings` cross from research_agent to V4State. Citations are assembled in Python from `findings[*].source_urls`; the formatter LLM emits ONLY bullet text. `TOTAL_SECTIONS=1`. Prompts in `research/overview/v4/prompts/`. Tunable via `OVERVIEW_V4_*` env vars (see below).
```

- [ ] **Step 2: Update the `task_type` description to include `rep:v4`**

Edit the same file. Find the paragraph beginning `**Database** (`db.py`)` and update the task_type list:

Old:

```markdown
Contains `save_research_task()` for persisting research usage data (including model, token costs, search tool, cost per search, environment, and `task_type` — `"rep:v1"` / `"rep:v2"` / `"rep:v3"` for overview research, `"election"`, or `"issue"`; the suffix encodes the overview pipeline version)
```

New:

```markdown
Contains `save_research_task()` for persisting research usage data (including model, token costs, search tool, cost per search, environment, and `task_type` — `"rep:v1"` / `"rep:v2"` / `"rep:v3"` / `"rep:v4"` for overview research, `"election"`, or `"issue"`; the suffix encodes the overview pipeline version)
```

- [ ] **Step 3: Update the `OVERVIEW_PIPELINE_VERSION` env var description**

Find the line that documents `OVERVIEW_PIPELINE_VERSION`:

Old:

```markdown
- `OVERVIEW_PIPELINE_VERSION` — which rep overview pipeline to run: `v1` (default, 5 section agents), `v2` (sections → synthesis bullets), or `v3` (static-query fan-out → distill bullets). Read at import time by `research/overview/__init__.py`; also encoded into `research_tasks.task_type` (`rep:v1`/`rep:v2`/`rep:v3`) and into Langfuse trace names.
```

New:

```markdown
- `OVERVIEW_PIPELINE_VERSION` — which rep overview pipeline to run: `v1` (default, 5 section agents), `v2` (sections → synthesis bullets), `v3` (static-query fan-out → distill bullets), or `v4` (LangGraph breadth + adaptive depth). Read at import time by `research/overview/__init__.py`; also encoded into `research_tasks.task_type` (`rep:v1`/`rep:v2`/`rep:v3`/`rep:v4`) and into Langfuse trace names.
```

- [ ] **Step 4: Add the v4 env vars after the v3 block**

Find the last `OVERVIEW_V3_*` env var line:

Old:

```markdown
- `OVERVIEW_V3_SNIPPET_CHAR_CAP` — v3 only: max chars per snippet before distillation (default `800`)
- `LANGFUSE_SECRET_KEY` — Langfuse tracing secret key
```

New:

```markdown
- `OVERVIEW_V3_SNIPPET_CHAR_CAP` — v3 only: max chars per snippet before distillation (default `800`)
- `OVERVIEW_V4_NUM_QUERIES` — v4 only: number of breadth queries (default `18`)
- `OVERVIEW_V4_RESULTS_PER_QUERY` — v4 only: Tavily results per query (default `5`)
- `OVERVIEW_V4_SEARCH_CONCURRENCY` — v4 only: max in-flight Tavily calls (default `5`)
- `OVERVIEW_V4_RESULTS_CEILING` — v4 only: cap on total results fed to research_agent (default `60`)
- `OVERVIEW_V4_SNIPPET_CHAR_CAP` — v4 only: max chars per snippet (default `800`)
- `OVERVIEW_V4_AGENT_MAX_DEPTH_CALLS` — v4 only: max depth-research calls per pipeline run (default `3`)
- `OVERVIEW_V4_DEPTH_RECURSION_LIMIT` — v4 only: recursion limit per depth subagent (default `8`)
- `LANGFUSE_SECRET_KEY` — Langfuse tracing secret key
```

- [ ] **Step 5: Add v4 trace names to the Langfuse-debugging section**

Find the `**Trace names**` block:

Old:

```markdown
- Rep overview v3: `v3-research-pipeline`, `v3-query-gen`, `v3-distill` (no per-section spans — v3 fans out searches without section agents).
- Elections: `election-ballot-overview` (single sync LLM span).
```

New:

```markdown
- Rep overview v3: `v3-research-pipeline`, `v3-query-gen`, `v3-distill` (no per-section spans — v3 fans out searches without section agents).
- Rep overview v4: `v4-research-pipeline`, `v4-query-gen`, `v4-research-agent` (one span per pipeline run), `v4-formatter`. Depth subagent runs are nested LangChain spans under the research_agent span (no top-level `@observe` on the depth subgraph — its work is part of the research_agent's trace tree).
- Elections: `election-ballot-overview` (single sync LLM span).
```

Also update the cross-reference paragraph to include v4:

Old:

```markdown
**Cross-reference to the DB:** `research_tasks.task_type` encodes the pipeline variant — `rep:v1` / `rep:v2` / `rep:v3` / `election` / `issue`.
```

New:

```markdown
**Cross-reference to the DB:** `research_tasks.task_type` encodes the pipeline variant — `rep:v1` / `rep:v2` / `rep:v3` / `rep:v4` / `election` / `issue`.
```

- [ ] **Step 6: Verify CLAUDE.md still parses (no broken markdown)**

```bash
head -100 /Users/andrewbarry/projects/my-representatives/CLAUDE.md
```

Eyeball the headings and bullets — make sure no merge artifacts and the v4 bullet sits in the right list.

- [ ] **Step 7: Commit**

```bash
cd /Users/andrewbarry/projects/my-representatives
git add CLAUDE.md
git commit -m "docs(claude.md): add v4 pipeline, env vars, and trace names"
```

---

## Task 18: Append v4 section to docs/rep-overview-versions.md

**Files:**
- Modify: `docs/rep-overview-versions.md`

The user already has unstaged edits in this file (per their IDE state at planning time). Before editing, confirm the file is in a state that lets the v4 section be cleanly appended.

- [ ] **Step 1: Inspect current state of the file**

```bash
cd /Users/andrewbarry/projects/my-representatives
git status docs/rep-overview-versions.md
git diff docs/rep-overview-versions.md | head -80
```

If the user has unstaged changes, ASK the user before continuing whether to (a) commit their changes first, (b) stash them, or (c) coordinate the v4 append with their in-progress edits. Do NOT overwrite their work.

- [ ] **Step 2: Append the v4 section**

Find the `## V3: Search-Outside-the-Loop + Single Distillation` section and the `---` separator after it. Insert the new v4 section BEFORE the `## The Fundamental Tension` heading. The exact insertion point depends on the user's in-progress edits — if their edits already touch v4 in any way, coordinate with them rather than blindly inserting.

The new section to insert:

```markdown
## V4: LangGraph Breadth + Adaptive Depth

**Architecture:** v3's breadth-first search posture, plus an optional depth pass for volatile subtopics, expressed as a LangGraph `StateGraph(V4State)` with two nested compiled subgraphs. State isolation across subgraph boundaries replaces v1/v2's per-section agents and prevents token accumulation.

**Backend:** `research/overview/v4/pipeline.py`
**Frontend:** shares `components/overview/bullets/` with v2/v3 (dispatched by response shape in `components/overview/index.tsx`)
**Prompts:** `research/overview/v4/prompts/` (`query_gen_*`, `research_agent_*`, `depth_agent_*`, `formatter_*`)

**How it works:**
1. **query_generator** — 1 LLM call with `with_structured_output(_QueryList)` emits `OVERVIEW_V4_NUM_QUERIES` (default 18) breadth-first queries. No tools.
2. **breadth_search** — Tavily fan-out bounded by `OVERVIEW_V4_SEARCH_CONCURRENCY` (default 5), `OVERVIEW_V4_RESULTS_PER_QUERY` results per query (default 5). No LLM.
3. **filter** — heuristic dedupe by URL, snippet truncation, total cap (`OVERVIEW_V4_RESULTS_CEILING`, default 60).
4. **research_agent** — compiled subgraph (`StateGraph(ResearchAgentState)`) with three nodes: `agent` (LLM bound to `request_depth_research`), `tools` (`ToolNode`), `finalize` (extracts structured `Finding` list via `with_structured_output`). The agent's prompt directs it to call depth research only for volatile claims (controversies, pending litigation, candidacy status, breaking news), capped at `OVERVIEW_V4_AGENT_MAX_DEPTH_CALLS` (default 3) calls per run.
5. **depth_subgraph** — same three-node pattern as the research_agent, but bound to the Tavily `web_search` tool. Per-topic isolated `DepthState`. The `request_depth_research` tool returns a `Command(update={"depth_findings": [...], "messages": [ToolMessage(...)]})` so depth findings flow into the research_agent's state without exposing the depth subagent's full message history.
6. **formatter** — 1 LLM call with `with_structured_output(_FormatterBullets)` emits ONLY bullet text. The unified citation list is assembled in Python from `findings[*].source_urls` against the filtered_results pool — never round-tripped through the LLM. `_FormatterBullets` is a single `BulletList` field, the smallest possible schema (no nullable union, no Optional), inheriting the v2 stringified-array fix.
- `TOTAL_SECTIONS = 1`; the store completes once at the end.

**What v4 is trying to fix:**
- v3's lack of adaptive search — controversies/litigation/candidacy claims could be stale because v3 has no way to refresh on demand.
- v1/v2's token accumulation — the agent loop pattern caused snippet re-reads on every LLM turn. v4 solves this with **state isolation across subgraphs**: the research_agent never sees a depth subagent's `messages`, only its structured findings. Each subgraph has its own context window scope.
- v2's stringified-bullets bug — formatter emits only `bullets` (no citations field), so the schema stays minimal.

**Tradeoffs:**
- **Latency floor higher than v3.** v3 is 2 LLM calls (query_gen + distill). v4 is at minimum 3 (query_gen + research_agent + formatter), more if the agent calls depth.
- **Agent recursion still possible.** Even with state isolation across subgraphs, the research_agent's own ReAct loop can spiral. Mitigated by `recursion_limit=12` and the prompt-enforced depth-call budget.
- **Depth-trigger quality is a prompt-engineering concern**, not an architecture concern — tunable after observation.

---

```

- [ ] **Step 3: Verify the file still parses**

```bash
head -250 /Users/andrewbarry/projects/my-representatives/docs/rep-overview-versions.md
```

Eyeball: v4 section appears between v3 and the Fundamental-Tension section.

- [ ] **Step 4: Commit (only the v4 section, not unrelated edits if any)**

```bash
cd /Users/andrewbarry/projects/my-representatives
git add -p docs/rep-overview-versions.md   # interactively stage only the v4 hunk
git commit -m "docs: add v4 section to rep-overview-versions.md"
```

If `git add -p` is impractical (e.g. heavy interleaving with the user's edits), ASK the user how to proceed rather than committing the whole file.

---

## End of plan

After Task 18 completes, the v4 pipeline is fully implemented, wired into the version-dispatch system, and documented. To activate v4 for the running app, set `OVERVIEW_PIPELINE_VERSION=v4` in `.env` (or as an env var when running uvicorn). Verify with the smoke test in Task 16 if not already done.
