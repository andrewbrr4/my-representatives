# Rep Overview Pipeline v1.1 + v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two new rep overview pipeline versions (`v1_1`, `v2`) alongside the existing `v1`, selectable via an env var, producing a tight blended bullets output. See the full design at `docs/superpowers/specs/2026-04-19-overview-pipeline-v1_1-v2-design.md`.

**Architecture:** Extend `backend/research/overview/` with two new sibling packages. Share only the Pydantic output model (`BulletsResearchSummary`) via `research/overview/shared/`. Each version owns its own pipeline code, prompts, and section agents — no cross-version imports. `research/overview/__init__.py` dispatches to the active version based on `OVERVIEW_PIPELINE_VERSION`. Router and cache become version-aware via a small interface change.

**Tech Stack:** FastAPI, LangChain, Anthropic Claude, Tavily, asyncpg, Redis, Pydantic, React + TypeScript.

**Test strategy note:** The repo has no existing pytest harness. For pure helpers (citation renumber, URL dedup, snippet truncate), we'll add targeted tests under `backend/research/overview/shared/tests/` with a minimal `conftest.py` and rely on `python -m pytest` (pytest is already a transitive dependency of langchain's dev extras; if missing on the executor's machine, they should `pip install pytest pytest-asyncio`). LLM-calling code (section agents, synthesis, query-gen, distillation) is verified end-to-end manually because mocking LangChain agents is more work than it's worth for this feature. Each LLM-calling task includes a manual smoke step with the exact commands to run.

---

## Phase 1 — Shared scaffolding

### Task 1: Create `BulletsResearchSummary` shared schema

**Files:**
- Create: `backend/research/overview/shared/__init__.py`
- Create: `backend/research/overview/shared/models.py`
- Create: `backend/research/overview/shared/tests/__init__.py`

- [ ] **Step 1: Create the `shared` package `__init__.py`**

Create `backend/research/overview/shared/__init__.py`:

```python
from .models import BulletsResearchSummary

__all__ = ["BulletsResearchSummary"]
```

- [ ] **Step 2: Create the shared Pydantic model**

Create `backend/research/overview/shared/models.py`:

```python
"""Shared output schema for rep overview versions v1.1+ that emit a single
blended bullet list (no per-section breakdown).

Version-specific pipelines (v1_1, v2) re-export this as ``ResearchSummary``
from their own ``__init__.py`` so ``research.overview.__init__.py`` dispatch
works transparently.
"""

from pydantic import BaseModel, Field

from models import Citation


class BulletsResearchSummary(BaseModel):
    """5–8 one-liner bullets blended across all topics, with a unified citation list.

    Each bullet may contain inline markers like ``[1]`` / ``[2]`` referencing
    1-indexed positions in ``citations``.
    """

    bullets: list[str] | None = Field(
        default=None,
        description="5–8 one-liner bullets. None means still loading.",
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Unified, renumbered citation list. 1-indexed by inline [N] markers in bullets.",
    )
```

- [ ] **Step 3: Create `shared/tests/__init__.py`**

Create `backend/research/overview/shared/tests/__init__.py` as an empty file (so pytest collects it as a package).

Run: `cd /Users/andrewbarry/projects/my-representatives/backend && touch research/overview/shared/tests/__init__.py`

- [ ] **Step 4: Smoke-import the new module**

Run from repo root:

```bash
cd backend && python -c "from research.overview.shared.models import BulletsResearchSummary; s = BulletsResearchSummary(); print(s.model_dump_json())"
```

Expected output: `{"bullets":null,"citations":[]}`

- [ ] **Step 5: Commit**

```bash
git add backend/research/overview/shared/
git commit -m "feat(overview): add shared BulletsResearchSummary schema"
```

---

### Task 2: Make `RepCache` version-aware

We add a `version: str` parameter to the cache interface so version flips isolate cached results without manual invalidation. Only the Rep cache changes — Election and Issue caches are untouched.

**Files:**
- Modify: `backend/store/interfaces.py`
- Modify: `backend/store/redis.py`

- [ ] **Step 1: Update the abstract interface**

Edit `backend/store/interfaces.py`, change the `RepCacheInterface` class to:

```python
class RepCacheInterface(ABC):
    @abstractmethod
    async def get(self, name: str, office: str, version: str) -> ResearchSummary | None: ...

    @abstractmethod
    async def put(self, name: str, office: str, version: str, summary: ResearchSummary) -> None: ...

    @abstractmethod
    async def cleanup(self) -> None: ...
```

Leave `ElectionCacheInterface` and `IssueCacheInterface` unchanged.

- [ ] **Step 2: Update `_cache_key` in redis.py**

Edit `backend/store/redis.py`, replace the `_cache_key` helper and the `RedisRepCache` class methods:

```python
def _cache_key(name: str, office: str, version: str) -> str:
    return f"repcache:{version}:{name.lower().strip()}|{office.lower().strip()}"


class RedisRepCache(RepCacheInterface):
    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    async def get(self, name: str, office: str, version: str) -> ResearchSummary | None:
        key = _cache_key(name, office, version)
        try:
            data = await self._r.get(key)
        except Exception as e:
            logger.error(f"Redis GET failed for {name} ({office}) [{version}]: {e}")
            return None
        if data is None:
            logger.debug(f"Cache miss for {name} ({office}) [{version}]")
            return None
        logger.info(f"Cache hit for {name} ({office}) [{version}]")
        return ResearchSummary.model_validate_json(data)

    async def put(self, name: str, office: str, version: str, summary: ResearchSummary) -> None:
        key = _cache_key(name, office, version)
        try:
            await self._r.set(key, summary.model_dump_json(), ex=REP_CACHE_TTL_SECONDS)
            logger.info(f"Cached research for {name} ({office}) [{version}], TTL={REP_CACHE_TTL_SECONDS}s")
        except Exception as e:
            logger.error(f"Redis SET failed for {name} ({office}) [{version}]: {e}")

    async def cleanup(self) -> None:
        pass
```

- [ ] **Step 3: Check for any no-op cache fallback implementation**

Run:

```bash
cd backend && grep -rn "class.*RepCacheInterface" store/
```

If any class other than `RedisRepCache` inherits from `RepCacheInterface` (e.g., a no-op fallback), update its `get`/`put` signatures the same way (add `version: str`, ignore it). If there's no such class, skip.

- [ ] **Step 4: Router update — pass version to cache calls**

Edit `backend/routers/overview.py`. Import the active version from the overview package and pass it to the cache calls. Replace the imports block and the two cache-call sites:

Change:

```python
from research.overview import ResearchSummary, research_representative
```

to:

```python
from research.overview import ACTIVE_VERSION, ResearchSummary, TOTAL_SECTIONS, research_representative
```

Change:

```python
        if summary is not None:
            await rep_cache.put(rep.name, rep.office, summary)
        else:
            await store.fail(research_id)
```

to:

```python
        if summary is not None:
            await rep_cache.put(rep.name, rep.office, ACTIVE_VERSION, summary)
        else:
            await store.fail(research_id)
```

Change:

```python
        cached = await get_rep_cache().get(rep.name, rep.office)
```

to:

```python
        cached = await get_rep_cache().get(rep.name, rep.office, ACTIVE_VERSION)
```

Change:

```python
    await store.create(research_id, summary=ResearchSummary())
```

to:

```python
    await store.create(research_id, total_sections=TOTAL_SECTIONS, summary=ResearchSummary())
```

(This also prepares the store for v1.1/v2's `total_sections=1`.)

- [ ] **Step 5: Verify backend still imports**

Run:

```bash
cd backend && python -c "import routers.overview; print('ok')"
```

This will fail until Task 3 adds `TOTAL_SECTIONS` and `ACTIVE_VERSION` exports. Continue.

- [ ] **Step 6: Commit**

```bash
git add backend/store/interfaces.py backend/store/redis.py backend/routers/overview.py
git commit -m "feat(cache): add version parameter to RepCache get/put"
```

---

### Task 3: Export `TOTAL_SECTIONS` + `ACTIVE_VERSION` from v1

**Files:**
- Modify: `backend/research/overview/v1/__init__.py`

- [ ] **Step 1: Add `TOTAL_SECTIONS` to the v1 package**

Replace the entire contents of `backend/research/overview/v1/__init__.py`:

```python
from .models import ResearchSummary
from .pipeline import research_representative

TOTAL_SECTIONS = 5

__all__ = ["ResearchSummary", "research_representative", "TOTAL_SECTIONS"]
```

- [ ] **Step 2: Commit**

```bash
git add backend/research/overview/v1/__init__.py
git commit -m "feat(overview/v1): export TOTAL_SECTIONS"
```

---

### Task 4: Env-var dispatch in `research/overview/__init__.py`

**Files:**
- Modify: `backend/research/overview/__init__.py`

- [ ] **Step 1: Rewrite the overview package `__init__.py`**

Replace the entire contents of `backend/research/overview/__init__.py`:

```python
"""Dispatch to the active rep overview pipeline version.

Selected at import time via the ``OVERVIEW_PIPELINE_VERSION`` env var.
Supported values: ``v1`` (default), ``v1_1``, ``v2``.

Each version's package must export ``ResearchSummary``,
``research_representative``, and ``TOTAL_SECTIONS``.
"""

import os

ACTIVE_VERSION = os.getenv("OVERVIEW_PIPELINE_VERSION", "v1")

if ACTIVE_VERSION == "v1":
    from .v1 import ResearchSummary, TOTAL_SECTIONS, research_representative
elif ACTIVE_VERSION == "v1_1":
    from .v1_1 import ResearchSummary, TOTAL_SECTIONS, research_representative
elif ACTIVE_VERSION == "v2":
    from .v2 import ResearchSummary, TOTAL_SECTIONS, research_representative
else:
    raise ValueError(
        f"Unknown OVERVIEW_PIPELINE_VERSION: {ACTIVE_VERSION!r}. "
        "Expected one of: v1, v1_1, v2."
    )

__all__ = [
    "ACTIVE_VERSION",
    "ResearchSummary",
    "TOTAL_SECTIONS",
    "research_representative",
]
```

- [ ] **Step 2: Verify default dispatch still loads v1**

Run:

```bash
cd backend && python -c "from research.overview import ACTIVE_VERSION, ResearchSummary, TOTAL_SECTIONS; print(ACTIVE_VERSION, TOTAL_SECTIONS, ResearchSummary.__module__)"
```

Expected output: `v1 5 research.overview.v1.models`

- [ ] **Step 3: Verify router imports resolve**

Run:

```bash
cd backend && python -c "import routers.overview; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/research/overview/__init__.py
git commit -m "feat(overview): env-var dispatch for pipeline version"
```

---

## Phase 2 — v1.1 (section agents + synthesis)

### Task 5: Create v1_1 directory, copy prompts, re-export schema

**Files:**
- Create: `backend/research/overview/v1_1/__init__.py`
- Create: `backend/research/overview/v1_1/models.py`
- Create: `backend/research/overview/v1_1/prompts/` (10 copied + 2 new, see below)

- [ ] **Step 1: Create the v1_1 directory and copy the 10 section prompts from v1**

Run from repo root:

```bash
mkdir -p backend/research/overview/v1_1/prompts
cp backend/research/overview/v1/prompts/policy_positions_system.txt backend/research/overview/v1_1/prompts/
cp backend/research/overview/v1/prompts/policy_positions_user.txt backend/research/overview/v1_1/prompts/
cp backend/research/overview/v1/prompts/recent_legislative_record_system.txt backend/research/overview/v1_1/prompts/
cp backend/research/overview/v1/prompts/recent_legislative_record_user.txt backend/research/overview/v1_1/prompts/
cp backend/research/overview/v1/prompts/accomplishments_system.txt backend/research/overview/v1_1/prompts/
cp backend/research/overview/v1/prompts/accomplishments_user.txt backend/research/overview/v1_1/prompts/
cp backend/research/overview/v1/prompts/controversies_system.txt backend/research/overview/v1_1/prompts/
cp backend/research/overview/v1/prompts/controversies_user.txt backend/research/overview/v1_1/prompts/
cp backend/research/overview/v1/prompts/top_donors_system.txt backend/research/overview/v1_1/prompts/
cp backend/research/overview/v1/prompts/top_donors_user.txt backend/research/overview/v1_1/prompts/
```

- [ ] **Step 2: Create `v1_1/models.py` that re-exports the shared schema**

Create `backend/research/overview/v1_1/models.py`:

```python
"""v1.1 re-exports the shared BulletsResearchSummary as ResearchSummary.

The schema is shared because the design treats it as a cross-version contract,
not version-specific logic. All section-agent code and prompts are owned
by v1.1 directly and do not import from v1.
"""

from research.overview.shared.models import BulletsResearchSummary as ResearchSummary

__all__ = ["ResearchSummary"]
```

- [ ] **Step 3: Create placeholder `v1_1/__init__.py`**

Create `backend/research/overview/v1_1/__init__.py`:

```python
from .models import ResearchSummary
from .pipeline import research_representative

TOTAL_SECTIONS = 1

__all__ = ["ResearchSummary", "research_representative", "TOTAL_SECTIONS"]
```

(This won't import yet — `pipeline.py` is created in Task 6. We write it now so we don't forget to add `TOTAL_SECTIONS`.)

- [ ] **Step 4: Commit**

```bash
git add backend/research/overview/v1_1/
git commit -m "feat(overview/v1_1): scaffold package and copy section prompts from v1"
```

---

### Task 6: v1.1 section agents — standalone copy of v1's agent code

**Files:**
- Create: `backend/research/overview/v1_1/pipeline.py` (initial version — just the section agents, synthesis added in Task 9)

- [ ] **Step 1: Write the section-agent half of `v1_1/pipeline.py`**

Create `backend/research/overview/v1_1/pipeline.py` with the section-agent code copied from v1. Do NOT import anything from `research.overview.v1`. The synthesis step is added in Task 9.

```python
"""v1.1 overview pipeline.

Flow:
1. Run 5 per-section research agents concurrently (own copy of v1's structure).
2. Assemble a dossier + unified citation pool.
3. One non-tool LLM call synthesizes 5–8 blended bullets with inline [N] markers.

Nothing is imported from ``research.overview.v1``. This version owns its
section agents and prompts end-to-end.
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from string import Template

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langfuse import observe
from langfuse.langchain import CallbackHandler
from langchain.agents import create_agent
from pydantic import BaseModel

from models import Citation, ListSectionResult, Representative
from research.overview.v1_1.models import ResearchSummary
from research.search import web_search
from research.usage import UsageStats, UsageTracker
from store.research_store import InMemoryResearchStore

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# v1.1 owns its own semaphore — isolated from v1's.
_semaphore = asyncio.Semaphore(2)


@dataclass
class SectionConfig:
    name: str
    output_model: type[BaseModel]
    system_prompt_file: str
    user_prompt_file: str
    content_field: str  # "items" for ListSectionResult


SECTIONS: list[SectionConfig] = [
    SectionConfig(
        name="policy_positions",
        output_model=ListSectionResult,
        system_prompt_file="policy_positions_system.txt",
        user_prompt_file="policy_positions_user.txt",
        content_field="items",
    ),
    SectionConfig(
        name="recent_legislative_record",
        output_model=ListSectionResult,
        system_prompt_file="recent_legislative_record_system.txt",
        user_prompt_file="recent_legislative_record_user.txt",
        content_field="items",
    ),
    SectionConfig(
        name="accomplishments",
        output_model=ListSectionResult,
        system_prompt_file="accomplishments_system.txt",
        user_prompt_file="accomplishments_user.txt",
        content_field="items",
    ),
    SectionConfig(
        name="controversies",
        output_model=ListSectionResult,
        system_prompt_file="controversies_system.txt",
        user_prompt_file="controversies_user.txt",
        content_field="items",
    ),
    SectionConfig(
        name="top_donors",
        output_model=ListSectionResult,
        system_prompt_file="top_donors_system.txt",
        user_prompt_file="top_donors_user.txt",
        content_field="items",
    ),
]


@observe(name="v1_1-section-agent")
async def run_section_agent(
    rep: Representative, section: SectionConfig
) -> tuple[list[str], list[Citation], UsageStats]:
    """Run a focused agent for one section. Returns (items, citations, usage)."""
    langfuse_handler = CallbackHandler()
    usage_tracker = UsageTracker()
    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    )
    agent = create_agent(
        model,
        tools=[web_search],
        response_format=section.output_model,
    )

    system_template = Template((_PROMPTS_DIR / section.system_prompt_file).read_text())
    user_template = Template((_PROMPTS_DIR / section.user_prompt_file).read_text())

    system_prompt = system_template.substitute(current_date=date.today().isoformat())
    user_prompt = user_template.substitute(name=rep.name, office=rep.office)

    result = await agent.ainvoke(
        {
            "messages": [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        },
        config={
            "callbacks": [langfuse_handler, usage_tracker],
            "recursion_limit": 15,
            "run_name": f"v1_1:{section.name}:{rep.name}",
        },
    )

    structured = result["structured_response"]
    items: list[str] = getattr(structured, section.content_field)
    citations: list[Citation] = structured.citations
    logger.info(
        f"[v1_1] Section '{section.name}' complete for {rep.name}: "
        f"{len(citations)} citations"
    )
    return items, citations, usage_tracker.stats


# research_representative is added in Task 9 (after synthesis helpers exist).
```

- [ ] **Step 2: Verify the module imports cleanly (top-level imports only, no call yet)**

Run:

```bash
cd backend && python -c "from research.overview.v1_1 import pipeline; print(pipeline.SECTIONS[0].name)"
```

Expected: `policy_positions`

The package `__init__.py` will fail to import `research_representative` — that's expected until Task 9. Don't import the package itself yet.

- [ ] **Step 3: Commit**

```bash
git add backend/research/overview/v1_1/pipeline.py
git commit -m "feat(overview/v1_1): section agents (standalone copy of v1 structure)"
```

---

### Task 7: Citation renumbering + dossier builder helpers

These are pure functions and get unit tests.

**Files:**
- Create: `backend/research/overview/v1_1/synthesis_input.py`
- Create: `backend/research/overview/shared/tests/test_synthesis_input.py`

- [ ] **Step 1: Write the failing test**

Create `backend/research/overview/shared/tests/test_synthesis_input.py`:

```python
"""Tests for v1.1 dossier builder and citation renumbering."""

from models import Citation
from research.overview.v1_1.synthesis_input import build_dossier


def test_build_dossier_empty_sections():
    result = build_dossier([])
    assert result.dossier == ""
    assert result.unified_citations == []


def test_build_dossier_single_section():
    sections = [
        (
            "policy_positions",
            ["**Climate** - Supports the clean grid bill. [1]", "**Taxes** - Opposes the 2024 cut. [2]"],
            [
                Citation(title="NYT", url="https://nyt.example/a"),
                Citation(title="WSJ", url="https://wsj.example/b"),
            ],
        ),
    ]
    result = build_dossier(sections)

    assert "## policy_positions" in result.dossier
    assert "**Climate** - Supports the clean grid bill. [1]" in result.dossier
    assert "Sources:" in result.dossier
    assert "[1] https://nyt.example/a" in result.dossier
    assert "[2] https://wsj.example/b" in result.dossier
    assert len(result.unified_citations) == 2
    assert result.unified_citations[0].url == "https://nyt.example/a"


def test_build_dossier_renumbers_across_sections():
    """Two sections with [1]/[2] each — after merging, the second section's
    markers should be rewritten to [3]/[4]."""
    sections = [
        (
            "policy_positions",
            ["**A** - First. [1]", "**B** - Second. [2]"],
            [
                Citation(title="S1", url="https://s1.example"),
                Citation(title="S2", url="https://s2.example"),
            ],
        ),
        (
            "controversies",
            ["**C** - Third. [1]", "**D** - Fourth. [2]"],
            [
                Citation(title="S3", url="https://s3.example"),
                Citation(title="S4", url="https://s4.example"),
            ],
        ),
    ]
    result = build_dossier(sections)
    assert "**C** - Third. [3]" in result.dossier
    assert "**D** - Fourth. [4]" in result.dossier
    assert [c.url for c in result.unified_citations] == [
        "https://s1.example",
        "https://s2.example",
        "https://s3.example",
        "https://s4.example",
    ]


def test_build_dossier_skips_sections_with_empty_content():
    sections = [
        ("policy_positions", [], []),
        (
            "controversies",
            ["**X** - only. [1]"],
            [Citation(title="S1", url="https://s1.example")],
        ),
    ]
    result = build_dossier(sections)
    assert "## policy_positions" not in result.dossier
    assert "**X** - only. [1]" in result.dossier
    assert len(result.unified_citations) == 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd backend && python -m pytest research/overview/shared/tests/test_synthesis_input.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'research.overview.v1_1.synthesis_input'`.

(If `pytest` is not installed, run `pip install pytest` first.)

- [ ] **Step 3: Implement `build_dossier`**

Create `backend/research/overview/v1_1/synthesis_input.py`:

```python
"""Build the synthesis-step input: dossier text + unified citation pool.

The synthesis LLM sees one blob of text grouped by section with renumbered
``[N]`` markers, plus a single merged citation list. This keeps the synthesis
prompt small and its citation indexing unambiguous.
"""

import re
from dataclasses import dataclass

from models import Citation

_MARKER_PATTERN = re.compile(r"\[(\d+)\]")


@dataclass
class DossierResult:
    dossier: str
    unified_citations: list[Citation]


def _renumber_markers(item: str, offset: int) -> str:
    """Rewrite ``[N]`` → ``[N+offset]`` in one bullet string."""

    def _sub(match: re.Match[str]) -> str:
        n = int(match.group(1))
        return f"[{n + offset}]"

    return _MARKER_PATTERN.sub(_sub, item)


def build_dossier(
    sections: list[tuple[str, list[str], list[Citation]]],
) -> DossierResult:
    """Merge per-section items/citations into one dossier blob + unified list.

    ``sections`` is an ordered list of ``(section_name, items, citations)``.
    Sections with no items are skipped entirely. Inline ``[N]`` markers in
    items are rewritten so they point at 1-indexed positions in the returned
    ``unified_citations`` list.
    """
    unified: list[Citation] = []
    blocks: list[str] = []

    for section_name, items, citations in sections:
        if not items:
            continue
        offset = len(unified)
        renumbered_items = [_renumber_markers(item, offset) for item in items]
        unified.extend(citations)

        lines = [f"## {section_name}"]
        lines.extend(f"- {item}" for item in renumbered_items)
        if citations:
            lines.append("")
            lines.append("Sources:")
            lines.extend(
                f"[{offset + i + 1}] {c.url}" for i, c in enumerate(citations)
            )
        blocks.append("\n".join(lines))

    return DossierResult(
        dossier="\n\n".join(blocks),
        unified_citations=unified,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd backend && python -m pytest research/overview/shared/tests/test_synthesis_input.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/research/overview/v1_1/synthesis_input.py backend/research/overview/shared/tests/test_synthesis_input.py
git commit -m "feat(overview/v1_1): dossier builder with unified citation renumbering"
```

---

### Task 8: Write v1.1 synthesis prompts

**Files:**
- Create: `backend/research/overview/v1_1/prompts/synthesis_system.txt`
- Create: `backend/research/overview/v1_1/prompts/synthesis_user.txt`

- [ ] **Step 1: Write the synthesis system prompt**

Create `backend/research/overview/v1_1/prompts/synthesis_system.txt`:

```
You are a nonpartisan political research synthesizer. You will receive a dossier of pre-researched findings about an elected official, grouped by topic (policy positions, recent legislative record, accomplishments, controversies, top donors). Your job is to distill the dossier into a tight, voter-useful overview.

Today's date is ${current_date}.

## Output requirements

- Produce exactly 5–8 bullets total. Fewer is better than padding.
- Each bullet is a single one-liner (roughly one short sentence, ~15–30 words).
- Bullets blend across topics — do NOT group by section. Pick the most important, best-sourced facts across all topics and order them by significance to a voter.
- Use the format `**3-6 word headline** - one short sentence of detail [N].` where `[N]` is one or more citation markers drawn from the provided unified citation list.
- Every factual claim must carry at least one `[N]` citation marker.

## Strict rules

- Only cite sources from the provided unified citation list. Do NOT invent sources, URLs, or facts.
- If two sections of the dossier contradict each other, prefer the better-sourced or more recent claim. You may silently drop the weaker claim.
- Omit anything weakly supported. A shorter overview is better than a padded one.
- Present facts neutrally. No editorializing.
- Do not output a heading, intro line, or summary paragraph — output the bullets only.
- Do not output a "sources" list yourself — the citations field of your structured output is the source of truth.
```

- [ ] **Step 2: Write the synthesis user prompt**

Create `backend/research/overview/v1_1/prompts/synthesis_user.txt`:

```
Official: $name
Office: $office

Below is the pre-researched dossier, grouped by topic. Inline `[N]` markers refer to positions in the unified citation list that follows this message.

---

$dossier

---

Unified citation list (1-indexed, matches `[N]` markers above):

$citations_block

---

Produce 5–8 blended bullets per the system instructions. Set the `bullets` field to the list of bullet strings and the `citations` field to the full unified citation list (copy it through unchanged — downstream code uses your `citations` field as the source of truth).
```

- [ ] **Step 3: Commit**

```bash
git add backend/research/overview/v1_1/prompts/synthesis_system.txt backend/research/overview/v1_1/prompts/synthesis_user.txt
git commit -m "feat(overview/v1_1): synthesis prompts"
```

---

### Task 9: v1.1 synthesis step + wire up `research_representative`

**Files:**
- Modify: `backend/research/overview/v1_1/pipeline.py`

- [ ] **Step 1: Append synthesis + orchestrator to `v1_1/pipeline.py`**

Append to the end of `backend/research/overview/v1_1/pipeline.py`:

```python
from research.overview.v1_1.synthesis_input import DossierResult, build_dossier


def _format_citations_block(citations: list[Citation]) -> str:
    if not citations:
        return "(none)"
    return "\n".join(
        f"[{i + 1}] {c.title} — {c.url}" for i, c in enumerate(citations)
    )


@observe(name="v1_1-synthesis")
async def run_synthesis(
    rep: Representative, dossier_result: DossierResult
) -> tuple[ResearchSummary, UsageStats]:
    """Non-tool LLM call that collapses the dossier into 5–8 bullets."""
    langfuse_handler = CallbackHandler()
    usage_tracker = UsageTracker()

    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    )
    structured_model = model.with_structured_output(ResearchSummary)

    system_template = Template((_PROMPTS_DIR / "synthesis_system.txt").read_text())
    user_template = Template((_PROMPTS_DIR / "synthesis_user.txt").read_text())

    system_prompt = system_template.substitute(current_date=date.today().isoformat())
    user_prompt = user_template.substitute(
        name=rep.name,
        office=rep.office,
        dossier=dossier_result.dossier or "(no section content returned)",
        citations_block=_format_citations_block(dossier_result.unified_citations),
    )

    result = await structured_model.ainvoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
        config={
            "callbacks": [langfuse_handler, usage_tracker],
            "run_name": f"v1_1:synthesis:{rep.name}",
        },
    )

    # Enforce: citations drawn from the pool, not invented.
    # Trust the model's copy-through but fall back to the unified pool if empty.
    if not result.citations:
        result = ResearchSummary(
            bullets=result.bullets,
            citations=dossier_result.unified_citations,
        )

    logger.info(
        f"[v1_1] Synthesis complete for {rep.name}: "
        f"{len(result.bullets or [])} bullets / {len(result.citations)} citations"
    )
    return result, usage_tracker.stats


@observe(name="v1_1-research-pipeline")
async def research_representative(
    rep: Representative,
    store: InMemoryResearchStore | None = None,
    research_id: str | None = None,
) -> tuple[ResearchSummary | None, UsageStats]:
    """Run 5 section agents concurrently, then synthesize into blended bullets."""
    total_usage = UsageStats()
    usage_lock = asyncio.Lock()
    logger.info(f"[v1_1] Queued research for {rep.name}")

    section_results: dict[str, tuple[list[str], list[Citation]]] = {}
    section_lock = asyncio.Lock()

    async def _run_section(section: SectionConfig) -> None:
        try:
            items, citations, usage = await run_section_agent(rep, section)
        except Exception as e:
            logger.error(
                f"[v1_1] Section '{section.name}' failed for {rep.name}: {e}",
                exc_info=e,
            )
            items = []
            citations = []
            usage = UsageStats()

        async with usage_lock:
            nonlocal total_usage
            total_usage += usage
        async with section_lock:
            section_results[section.name] = (items, citations)

    async with _semaphore:
        logger.info(f"[v1_1] Starting research for {rep.name}")
        try:
            await asyncio.gather(*(_run_section(section) for section in SECTIONS))
        except Exception as e:
            logger.error(f"[v1_1] Section phase failed for {rep.name}: {e}", exc_info=True)
            return None, total_usage

        # Preserve section ordering from SECTIONS (deterministic dossier).
        ordered = [
            (s.name, *section_results.get(s.name, ([], []))) for s in SECTIONS
        ]
        dossier_result = build_dossier(ordered)

        try:
            summary, synth_usage = await run_synthesis(rep, dossier_result)
        except Exception as e:
            logger.error(f"[v1_1] Synthesis failed for {rep.name}: {e}", exc_info=True)
            return None, total_usage

        async with usage_lock:
            total_usage += synth_usage

        if store and research_id:
            # total_sections=1 → a single complete_section call moves the task to "complete"
            await store.complete_section(
                research_id,
                "overview",
                summary.bullets or [],
                summary.citations,
            )

        logger.info(
            f"[v1_1] Research for {rep.name}: "
            f"{total_usage.input_tokens} in / {total_usage.output_tokens} out / "
            f"{total_usage.tool_calls} tool calls"
        )
        return summary, total_usage
```

- [ ] **Step 2: Verify the v1_1 package imports cleanly**

Run:

```bash
cd backend && python -c "from research.overview.v1_1 import ResearchSummary, TOTAL_SECTIONS, research_representative; print(TOTAL_SECTIONS, ResearchSummary.model_fields.keys())"
```

Expected: `1 dict_keys(['bullets', 'citations'])`

- [ ] **Step 3: Verify dispatch resolves v1_1**

Run:

```bash
cd backend && OVERVIEW_PIPELINE_VERSION=v1_1 python -c "from research.overview import ACTIVE_VERSION, TOTAL_SECTIONS, ResearchSummary; print(ACTIVE_VERSION, TOTAL_SECTIONS, list(ResearchSummary.model_fields.keys()))"
```

Expected: `v1_1 1 ['bullets', 'citations']`

- [ ] **Step 4: Commit**

```bash
git add backend/research/overview/v1_1/pipeline.py
git commit -m "feat(overview/v1_1): synthesis step + orchestrator"
```

---

## Phase 3 — v2 (breadth-first retrieval + distillation)

### Task 10: Add raw Tavily helper to `research/search.py`

**Files:**
- Modify: `backend/research/search.py`

- [ ] **Step 1: Append `tavily_search_raw` to `search.py`**

Append to the end of `backend/research/search.py`:

```python
async def tavily_search_raw(
    query: str, max_results: int = 5
) -> list[dict[str, str]]:
    """Run one Tavily search and return raw results as a list of dicts.

    Used by non-agent pipelines (e.g. overview v2) that execute searches
    outside the LangChain agent loop to avoid accumulating search results
    in LLM context. Returns ``[]`` on failure (caller logs + proceeds).
    Each result is ``{"title": str, "url": str, "snippet": str}``.
    """
    async with _search_semaphore:
        tavily = _get_tavily_client()
        for attempt in range(_MAX_SEARCH_RETRIES):
            try:
                search_results = await tavily.search(query=query, max_results=max_results)
                return [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("content", ""),
                    }
                    for r in search_results.get("results", [])
                ]
            except Exception as e:
                error_detail = str(e)
                if hasattr(e, "response"):
                    try:
                        error_detail = e.response.text
                    except Exception:
                        pass
                is_rate_limit = "429" in error_detail or "rate" in error_detail.lower()
                if is_rate_limit and attempt < _MAX_SEARCH_RETRIES - 1:
                    delay = _RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(f"Raw search rate-limited, retrying in {delay}s (attempt {attempt + 1})")
                    await asyncio.sleep(delay)
                    continue
                logger.warning(f"Raw search failed for query={query!r}: {error_detail}")
                return []
    return []
```

- [ ] **Step 2: Smoke-test the helper**

Run (requires `TAVILY_API_KEY` in env):

```bash
cd backend && python -c "
import asyncio
from research.search import tavily_search_raw
res = asyncio.run(tavily_search_raw('US Senator Bernie Sanders recent votes', max_results=2))
print(len(res), res[0].keys() if res else 'no results')
"
```

Expected: `2 dict_keys(['title', 'url', 'snippet'])` (or similar — at least one result with the three keys).

- [ ] **Step 3: Commit**

```bash
git add backend/research/search.py
git commit -m "feat(search): add tavily_search_raw for non-agent pipelines"
```

---

### Task 11: v2 pre-filter helpers (dedup + snippet truncation)

Pure functions → unit tests.

**Files:**
- Create: `backend/research/overview/v2/__init__.py`
- Create: `backend/research/overview/v2/models.py`
- Create: `backend/research/overview/v2/prefilter.py`
- Create: `backend/research/overview/shared/tests/test_v2_prefilter.py`

- [ ] **Step 1: Create v2 package skeleton**

Create `backend/research/overview/v2/models.py`:

```python
"""v2 re-exports the shared BulletsResearchSummary as ResearchSummary."""

from research.overview.shared.models import BulletsResearchSummary as ResearchSummary

__all__ = ["ResearchSummary"]
```

Create `backend/research/overview/v2/__init__.py`:

```python
from .models import ResearchSummary
from .pipeline import research_representative

TOTAL_SECTIONS = 1

__all__ = ["ResearchSummary", "research_representative", "TOTAL_SECTIONS"]
```

Create `backend/research/overview/v2/prompts/` as an empty directory:

```bash
mkdir -p backend/research/overview/v2/prompts
```

- [ ] **Step 2: Write the failing test**

Create `backend/research/overview/shared/tests/test_v2_prefilter.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
cd backend && python -m pytest research/overview/shared/tests/test_v2_prefilter.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'research.overview.v2.prefilter'`.

- [ ] **Step 4: Implement `prefilter_results`**

Create `backend/research/overview/v2/prefilter.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify success**

Run:

```bash
cd backend && python -m pytest research/overview/shared/tests/test_v2_prefilter.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/research/overview/v2/__init__.py backend/research/overview/v2/models.py backend/research/overview/v2/prefilter.py backend/research/overview/v2/prompts backend/research/overview/shared/tests/test_v2_prefilter.py
git commit -m "feat(overview/v2): scaffold package + prefilter helpers"
```

---

### Task 12: v2 query-generation and distillation prompts

**Files:**
- Create: `backend/research/overview/v2/prompts/query_gen_system.txt`
- Create: `backend/research/overview/v2/prompts/query_gen_user.txt`
- Create: `backend/research/overview/v2/prompts/distill_system.txt`
- Create: `backend/research/overview/v2/prompts/distill_user.txt`

- [ ] **Step 1: Query-generation system prompt**

Create `backend/research/overview/v2/prompts/query_gen_system.txt`:

```
You generate a diverse, high-coverage list of web search queries to research an elected official for a voter-facing overview.

Today's date is ${current_date}.

## Coverage angles to hit (aim to cover as many as relevant)

- Policy positions and stated beliefs
- Recent votes and legislation sponsored/co-sponsored
- Notable accomplishments and signed bills
- Controversies, ethics complaints, lawsuits, scandals
- Top donors and campaign finance
- Public statements and press coverage from reputable outlets
- Local/regional news about the official
- Biographical background relevant to their current office

## Rules

- Produce exactly $num_queries queries.
- Each query is a single search string (no boolean operators, no quotes around the whole thing).
- Queries should be diverse — do NOT produce rephrasings of the same question.
- Prefer queries that name the official explicitly and include specific angles (e.g. "Senator Jane Smith 2024 infrastructure vote" not "Jane Smith stuff").
- Include at least one query that targets recent controversies and at least one that targets campaign donors.
- Do NOT add a query that asks for a summary or biography of the official as a whole — the downstream step synthesizes. Your queries should retrieve specifics.
```

- [ ] **Step 2: Query-generation user prompt**

Create `backend/research/overview/v2/prompts/query_gen_user.txt`:

```
Generate exactly $num_queries diverse search queries to research $name, who serves as $office. Output a list of strings in the ``queries`` field of your structured output, nothing else.
```

- [ ] **Step 3: Distillation system prompt**

Create `backend/research/overview/v2/prompts/distill_system.txt`:

```
You are a nonpartisan political research synthesizer. You will receive a set of web search results (title + URL + snippet) about an elected official. Your job is to distill them into a tight, voter-useful overview and to produce a matching citation list.

Today's date is ${current_date}.

## Output requirements

- Produce exactly 5–8 bullets total. Fewer is better than padding.
- Each bullet is a single one-liner (~15–30 words).
- Bullets blend across topics (policy, votes, controversies, donors, etc.) and are ordered by significance to a voter.
- Use the format `**3-6 word headline** - one short sentence of detail [N].` where `[N]` is one or more citation markers.
- Every factual claim must carry at least one `[N]` citation marker.

## Citations

- Only cite URLs present in the provided search results. Do NOT invent URLs or facts.
- In your structured output, set the ``citations`` field to the ordered list of ``{title, url}`` objects you actually cited. Number them 1, 2, 3... matching the `[N]` markers in your bullets.
- If a single fact is supported by multiple results, you may cite several like `[1][3]`.

## Strict rules

- If two results conflict, prefer the better-sourced or more recent claim. Silently drop the weaker one.
- Omit anything weakly supported. A shorter overview beats a padded one.
- Present facts neutrally. No editorializing.
- Do not output a heading, intro line, or summary paragraph — output the bullets only (in the ``bullets`` field).
```

- [ ] **Step 4: Distillation user prompt**

Create `backend/research/overview/v2/prompts/distill_user.txt`:

```
Official: $name
Office: $office

Search results to distill:

$results_block

---

Produce 5–8 blended bullets per the system instructions. Populate the ``bullets`` and ``citations`` fields of your structured output. The ``citations`` field should contain only URLs that appear in the search results above, and must be ordered to match your inline `[N]` markers.
```

- [ ] **Step 5: Commit**

```bash
git add backend/research/overview/v2/prompts/
git commit -m "feat(overview/v2): query-gen and distillation prompts"
```

---

### Task 13: v2 query-generation step + pipeline orchestrator

**Files:**
- Create: `backend/research/overview/v2/pipeline.py`

- [ ] **Step 1: Write the full v2 pipeline**

Create `backend/research/overview/v2/pipeline.py`:

```python
"""v2 overview pipeline — breadth-first retrieval + single-shot distillation.

Flow:
1. Query generation (1 LLM call, no tools) → list of diverse search queries.
2. Parallel Tavily fan-out (no LLM in the loop).
3. Pre-filter (dedupe by URL, truncate snippets, cap total count).
4. Distillation (1 LLM call, no tools) → BulletsResearchSummary.
"""

import asyncio
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

from models import Representative
from research.overview.v2.models import ResearchSummary
from research.overview.v2.prefilter import prefilter_results
from research.search import tavily_search_raw
from research.usage import UsageStats, UsageTracker
from store.research_store import InMemoryResearchStore

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

_NUM_QUERIES = int(os.getenv("OVERVIEW_V2_NUM_QUERIES", "15"))
_RESULTS_PER_QUERY = int(os.getenv("OVERVIEW_V2_RESULTS_PER_QUERY", "5"))
_SEARCH_CONCURRENCY = int(os.getenv("OVERVIEW_V2_SEARCH_CONCURRENCY", "5"))
_RESULTS_CEILING = int(os.getenv("OVERVIEW_V2_RESULTS_CEILING", "60"))
_SNIPPET_CHAR_CAP = int(os.getenv("OVERVIEW_V2_SNIPPET_CHAR_CAP", "800"))


class _QueryList(BaseModel):
    queries: list[str] = Field(description="Diverse search queries, one per item.")


@observe(name="v2-query-gen")
async def generate_queries(rep: Representative) -> tuple[list[str], UsageStats]:
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
            "run_name": f"v2:query-gen:{rep.name}",
        },
    )
    queries = [q.strip() for q in result.queries if q and q.strip()]
    logger.info(f"[v2] Generated {len(queries)} queries for {rep.name}")
    return queries, usage_tracker.stats


async def run_searches(queries: list[str]) -> tuple[list[dict[str, str]], int]:
    """Run all queries in parallel with a concurrency bound.

    Returns ``(concatenated_results, num_successful_queries)``.
    A query is "successful" if it returned at least one result.
    """
    sem = asyncio.Semaphore(_SEARCH_CONCURRENCY)

    async def _run_one(q: str) -> list[dict[str, str]]:
        async with sem:
            return await tavily_search_raw(q, max_results=_RESULTS_PER_QUERY)

    per_query = await asyncio.gather(*(_run_one(q) for q in queries))
    concatenated: list[dict[str, str]] = []
    successful = 0
    for results in per_query:
        if results:
            successful += 1
            concatenated.extend(results)
    logger.info(
        f"[v2] Search phase: {successful}/{len(queries)} queries returned results; "
        f"{len(concatenated)} total raw results"
    )
    return concatenated, successful


def _format_results_block(results: list[dict[str, str]]) -> str:
    if not results:
        return "(no results)"
    lines: list[str] = []
    for i, r in enumerate(results, start=1):
        lines.append(f"[{i}] {r['title']}\n    URL: {r['url']}\n    {r['snippet']}")
    return "\n\n".join(lines)


@observe(name="v2-distill")
async def distill(
    rep: Representative, results: list[dict[str, str]]
) -> tuple[ResearchSummary, UsageStats]:
    langfuse_handler = CallbackHandler()
    usage_tracker = UsageTracker()

    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    )
    structured = model.with_structured_output(ResearchSummary)

    system_template = Template((_PROMPTS_DIR / "distill_system.txt").read_text())
    user_template = Template((_PROMPTS_DIR / "distill_user.txt").read_text())

    system_prompt = system_template.substitute(current_date=date.today().isoformat())
    user_prompt = user_template.substitute(
        name=rep.name, office=rep.office, results_block=_format_results_block(results)
    )

    summary = await structured.ainvoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
        config={
            "callbacks": [langfuse_handler, usage_tracker],
            "run_name": f"v2:distill:{rep.name}",
        },
    )
    logger.info(
        f"[v2] Distill complete for {rep.name}: "
        f"{len(summary.bullets or [])} bullets / {len(summary.citations)} citations"
    )
    return summary, usage_tracker.stats


@observe(name="v2-research-pipeline")
async def research_representative(
    rep: Representative,
    store: InMemoryResearchStore | None = None,
    research_id: str | None = None,
) -> tuple[ResearchSummary | None, UsageStats]:
    total_usage = UsageStats()
    logger.info(f"[v2] Starting research for {rep.name}")

    # 1. Query generation
    try:
        queries, usage = await generate_queries(rep)
    except Exception as e:
        logger.error(f"[v2] Query generation failed for {rep.name}: {e}", exc_info=True)
        return None, total_usage
    total_usage += usage
    if not queries:
        logger.error(f"[v2] Query generation returned no queries for {rep.name}")
        return None, total_usage

    # 2. Parallel search
    raw_results, successful_queries = await run_searches(queries)
    total_usage.tool_calls += successful_queries  # count billable Tavily calls
    if not raw_results:
        logger.error(f"[v2] All searches returned no results for {rep.name}")
        return None, total_usage

    # 3. Pre-filter
    filtered = prefilter_results(
        raw_results, snippet_char_cap=_SNIPPET_CHAR_CAP, ceiling=_RESULTS_CEILING
    )
    logger.info(f"[v2] Pre-filter: {len(raw_results)} → {len(filtered)} results")

    # 4. Distillation
    try:
        summary, usage = await distill(rep, filtered)
    except Exception as e:
        logger.error(f"[v2] Distillation failed for {rep.name}: {e}", exc_info=True)
        return None, total_usage
    total_usage += usage

    if store and research_id:
        await store.complete_section(
            research_id, "overview", summary.bullets or [], summary.citations
        )

    logger.info(
        f"[v2] Research for {rep.name}: "
        f"{total_usage.input_tokens} in / {total_usage.output_tokens} out / "
        f"{total_usage.tool_calls} tool calls"
    )
    return summary, total_usage
```

- [ ] **Step 2: Verify the v2 package imports**

Run:

```bash
cd backend && python -c "from research.overview.v2 import ResearchSummary, TOTAL_SECTIONS, research_representative; print(TOTAL_SECTIONS, list(ResearchSummary.model_fields.keys()))"
```

Expected: `1 ['bullets', 'citations']`

- [ ] **Step 3: Verify dispatch resolves v2**

Run:

```bash
cd backend && OVERVIEW_PIPELINE_VERSION=v2 python -c "from research.overview import ACTIVE_VERSION, TOTAL_SECTIONS; print(ACTIVE_VERSION, TOTAL_SECTIONS)"
```

Expected: `v2 1`

- [ ] **Step 4: Commit**

```bash
git add backend/research/overview/v2/pipeline.py
git commit -m "feat(overview/v2): breadth-first pipeline (query-gen, fan-out, distill)"
```

---

## Phase 4 — Frontend

### Task 14: Bullets rendering component

**Files:**
- Create: `frontend/src/components/overview/bullets/types.ts`
- Create: `frontend/src/components/overview/bullets/ResearchContent.tsx`
- Create: `frontend/src/components/overview/bullets/index.ts`

- [ ] **Step 1: Types**

Create `frontend/src/components/overview/bullets/types.ts`:

```typescript
/**
 * Shared rep overview schema for v1.1+ — a single blended bullet list
 * with a unified citation pool.
 */

import type { Citation } from "@/types";

export interface BulletsResearchSummary {
  bullets: string[] | null;
  citations: Citation[];
}
```

- [ ] **Step 2: Renderer**

Create `frontend/src/components/overview/bullets/ResearchContent.tsx`:

```tsx
/**
 * Bullets research content renderer — single blended bullet list with
 * inline citation markers resolved against a unified citation pool.
 *
 * Used by any overview pipeline version that produces a BulletsResearchSummary
 * (currently v1.1 and v2).
 */

import type { BulletsResearchSummary } from "./types";
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

export function ResearchContent({ summary }: { summary: BulletsResearchSummary }) {
  const { bullets, citations } = summary;

  if (bullets === null) {
    return (
      <div className="space-y-2 text-sm leading-relaxed prose prose-sm prose-neutral dark:prose-invert max-w-none">
        <BulletsSkeleton />
      </div>
    );
  }

  return (
    <div className="space-y-2 text-sm leading-relaxed prose prose-sm prose-neutral dark:prose-invert max-w-none">
      <ul className="list-disc pl-5 space-y-1">
        {bullets.map((b, i) => (
          <li key={i}>{renderInline(b, citations)}</li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 3: Barrel export**

Create `frontend/src/components/overview/bullets/index.ts`:

```typescript
export { ResearchContent } from "./ResearchContent";
export type { BulletsResearchSummary } from "./types";
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/overview/bullets/
git commit -m "feat(frontend): bullets rendering component for v1.1 + v2 overviews"
```

---

### Task 15: Shape-based dispatch in `overview/index.ts`

**Files:**
- Modify: `frontend/src/components/overview/index.ts`

- [ ] **Step 1: Replace `overview/index.ts` with shape-dispatched export**

Replace the entire contents of `frontend/src/components/overview/index.ts`:

```typescript
/**
 * Overview dispatch: the backend may return a v1 sectioned summary OR a
 * BulletsResearchSummary (v1.1, v2). Consumers get a single ResearchContent
 * component and a union type; the component picks a renderer at runtime
 * based on the response shape.
 */

import type { ResearchSummary as V1ResearchSummary } from "./v1";
import type { BulletsResearchSummary } from "./bullets";
import { ResearchContent as V1ResearchContent } from "./v1";
import { ResearchContent as BulletsResearchContent } from "./bullets";

export type ResearchSummary = V1ResearchSummary | BulletsResearchSummary;

export function isBullets(summary: ResearchSummary): summary is BulletsResearchSummary {
  return "bullets" in summary;
}

export function ResearchContent({ summary }: { summary: ResearchSummary }) {
  if (isBullets(summary)) {
    return <BulletsResearchContent summary={summary} />;
  }
  return <V1ResearchContent summary={summary} />;
}
```

- [ ] **Step 2: Rename the file to `.tsx` so JSX compiles**

Run:

```bash
git mv frontend/src/components/overview/index.ts frontend/src/components/overview/index.tsx
```

- [ ] **Step 3: Verify frontend type-checks**

Run:

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors. If `@/types` chain reports an error because `types/index.ts` imports `ResearchSummary` from `@/components/overview`, that's fine — the new shape is still a valid type export. If there's a specific error about `isBullets` or the component, re-read Step 1.

- [ ] **Step 4: Verify the dev server still builds**

Run:

```bash
cd frontend && npm run build 2>&1 | tail -30
```

Expected: build succeeds with no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/overview/index.tsx
git commit -m "feat(frontend): shape-based dispatch between v1 sections and bullets"
```

---

## Phase 5 — End-to-end verification

### Task 16: Verify v1 (default) still works

- [ ] **Step 1: Start the backend**

In one terminal:

```bash
conda activate my-reps
cd backend && uvicorn main:app --reload
```

- [ ] **Step 2: Start the frontend**

In another terminal:

```bash
cd frontend && npm run dev
```

- [ ] **Step 3: Manual smoke**

Open `http://localhost:5173`, enter a test address (e.g., "1600 Pennsylvania Ave NW, Washington, DC 20500"), click "Research" on any representative. Confirm the **five-section** layout appears with progressive fill-in and per-section citations. This is the unchanged v1 path.

- [ ] **Step 4: If broken — check the logs**

Backend log should show `Starting research for <name>` and 5 section completions. Frontend should show sections filling top-down. If it renders as bullets, the shape-dispatch is wrong — re-read Task 15. Stop and fix before moving on.

---

### Task 17: Verify v1.1 end-to-end

- [ ] **Step 1: Restart backend with `OVERVIEW_PIPELINE_VERSION=v1_1`**

Stop the backend from Task 16, then:

```bash
conda activate my-reps
cd backend && OVERVIEW_PIPELINE_VERSION=v1_1 uvicorn main:app --reload
```

The frontend does not need a restart.

- [ ] **Step 2: Clear rep cache (optional)**

If Redis is configured, clear only v1 keys to avoid confusion:

```bash
# optional — cache keys are already version-prefixed so this isn't strictly needed
redis-cli --scan --pattern 'repcache:v1:*' | xargs -r redis-cli del
```

- [ ] **Step 3: Manual smoke**

In the browser, enter a test address. Click Research on one rep.

Expected UI: a single bullet-list skeleton, then ~5–8 short bullets with inline `[N]` markers and a unified citation list. No per-section headings.

Expected backend logs (sample):

```
[v1_1] Starting research for <name>
[v1_1] Section 'policy_positions' complete for <name>: ...
[v1_1] Section 'recent_legislative_record' complete for <name>: ...
[v1_1] Section 'accomplishments' complete for <name>: ...
[v1_1] Section 'controversies' complete for <name>: ...
[v1_1] Section 'top_donors' complete for <name>: ...
[v1_1] Synthesis complete for <name>: N bullets / M citations
[v1_1] Research for <name>: <in> in / <out> out / <tools> tool calls
```

- [ ] **Step 4: Verify DB persistence**

With the Cloud SQL Auth Proxy or local Postgres running, confirm a `research_tasks` row was inserted with non-zero tokens and tool calls:

```bash
psql "$DATABASE_URL" -c "SELECT research_id, target, input_tokens, output_tokens, tool_calls, status FROM research_tasks ORDER BY created_at DESC LIMIT 3;"
```

Expected: the most recent row has `status=done`, non-zero `input_tokens` (section agents + synthesis combined), and `tool_calls` equal to the sum of Tavily searches the section agents ran.

---

### Task 18: Verify v2 end-to-end

- [ ] **Step 1: Restart backend with `OVERVIEW_PIPELINE_VERSION=v2`**

Stop the backend, then:

```bash
conda activate my-reps
cd backend && OVERVIEW_PIPELINE_VERSION=v2 uvicorn main:app --reload
```

- [ ] **Step 2: Manual smoke**

Browser → enter address → Research on one rep.

Expected UI: same bullet layout as v1.1.

Expected backend logs:

```
[v2] Starting research for <name>
[v2] Generated 15 queries for <name>
[v2] Search phase: X/15 queries returned results; N total raw results
[v2] Pre-filter: N → M results
[v2] Distill complete for <name>: K bullets / J citations
[v2] Research for <name>: <in> in / <out> out / 15 tool calls
```

- [ ] **Step 3: Verify DB persistence**

```bash
psql "$DATABASE_URL" -c "SELECT research_id, target, input_tokens, output_tokens, tool_calls, status FROM research_tasks ORDER BY created_at DESC LIMIT 3;"
```

Expected: row with non-zero tokens; `tool_calls` ≈ number of queries that returned results (up to `OVERVIEW_V2_NUM_QUERIES`).

- [ ] **Step 4: Verify cache isolation**

Click "Research" twice on the same rep while still under `v2`. Second click should return instantly with `research_id: "cached"` in backend logs. Then stop the backend and restart with `OVERVIEW_PIPELINE_VERSION=v1`. Click Research on that same rep. Should kick off a fresh v1 run (no cache hit), because the cache key is version-prefixed.

- [ ] **Step 5: Final commit marker (optional)**

If any fixups were required during verification, commit them:

```bash
git add -u && git commit -m "fixup: <describe what you fixed>"
```

Otherwise no commit here.

---

## Done criteria

- All three versions (`v1`, `v1_1`, `v2`) produce a rendered overview via the same frontend.
- `v1` still renders as five sections.
- `v1_1` and `v2` render as a bullet list.
- Each `research_tasks` row captures tokens and Tavily calls for its version.
- Switching `OVERVIEW_PIPELINE_VERSION` does not cross-contaminate cached results.
- No version imports section-agent code or prompts from another version.
