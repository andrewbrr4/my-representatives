# Overview Pipeline Restructure — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize `backend/research/overview/` so v4 is the flat, default pipeline at the top level and v1/v2/v3 live under a `legacy/` subdir — signalling that v4 is the path forward without removing the older variants.

**Architecture:** No behavior changes. Pure file-move + import-update + docs refactor.
- v4 modules (`pipeline.py`, `models.py`, `state.py`, `nodes/`, `tools/`, `prompts/`) move up one level, replacing the `v4/` subdir.
- v1/v2/v3 packages move into a new `legacy/` subdir.
- The `OVERVIEW_PIPELINE_VERSION` env var contract stays — defaults change from `v1` to `v4`; legacy values still dispatch correctly (now imported from `legacy.vN`).
- Cache version keys, trace names, env var names, and DB `task_type` strings are all unchanged. The `v4` literal stays as a generation marker so existing cache/analytics continuity is preserved.
- No new code, no behavior changes, no schema changes.

**Tech Stack:** Python 3.13, FastAPI, LangGraph. No tests in repo — verification is "backend imports cleanly + smoke-test all four env var values via a Python REPL invocation".

---

## File Structure (end state)

```
backend/research/overview/
├── __init__.py                  # rewritten dispatch; default=v4 (flat); legacy via env var
├── _bullet_coercion.py          # unchanged, stays top-level (legacy imports it from here)
├── models.py                    # was v4/models.py
├── pipeline.py                  # was v4/pipeline.py
├── state.py                     # was v4/state.py
├── prompts/                     # was v4/prompts/
│   ├── query_gen_system.txt
│   ├── query_gen_user.txt
│   ├── research_agent_system.txt
│   ├── research_agent_user.txt
│   ├── depth_agent_system.txt
│   ├── depth_agent_user.txt
│   ├── formatter_system.txt
│   └── formatter_user.txt
├── nodes/                       # was v4/nodes/
│   ├── __init__.py
│   ├── breadth_search.py
│   ├── depth_subgraph.py
│   ├── filter_node.py
│   ├── formatter.py
│   ├── query_generator.py
│   └── research_agent.py
├── tools/                       # was v4/tools/
│   ├── __init__.py
│   └── tavily_search.py
└── legacy/
    ├── __init__.py              # new, just a marker (no exports)
    ├── v1/                      # moved from research/overview/v1/
    ├── v2/                      # moved from research/overview/v2/
    └── v3/                      # moved from research/overview/v3/
```

Internal imports in v4 modules: `research.overview.v4.X` → `research.overview.X`.
Internal imports in legacy: `research.overview.v1.X` → `research.overview.legacy.v1.X` (and v2/v3).

---

## Task 1: Move v1/v2/v3 into `legacy/`

Move v1/v2/v3 first while v4 still lives in `v4/` — this keeps the diff bounded and lets us verify the env-var dispatch for the legacy paths before touching v4.

**Files:**
- Create: `backend/research/overview/legacy/__init__.py` (empty marker)
- Move (git mv): `backend/research/overview/v1/` → `backend/research/overview/legacy/v1/`
- Move (git mv): `backend/research/overview/v2/` → `backend/research/overview/legacy/v2/`
- Move (git mv): `backend/research/overview/v3/` → `backend/research/overview/legacy/v3/`
- Modify: `backend/research/overview/legacy/v1/pipeline.py` (one import line)
- Modify: `backend/research/overview/legacy/v2/pipeline.py` (three import lines)
- Modify: `backend/research/overview/legacy/v2/synthesis_input.py` (any internal v2 imports)
- Modify: `backend/research/overview/legacy/v3/pipeline.py` (two import lines)
- Modify: `backend/research/overview/legacy/v3/models.py` (one import line)
- Modify: `backend/research/overview/__init__.py` (dispatch updates for legacy)

- [ ] **Step 1: Create the `legacy/` package marker**

```bash
mkdir -p /Users/andrewbarry/projects/my-representatives/backend/research/overview/legacy
```

Create `backend/research/overview/legacy/__init__.py` with the Write tool, content:

```python
"""Legacy rep overview pipelines (v1, v2, v3).

These are kept available behind the ``OVERVIEW_PIPELINE_VERSION`` env var
for trace/cost comparison against the current default (v4). They are not
the focus of further iteration — new work belongs in the top-level
``research.overview`` package.
"""
```

- [ ] **Step 2: Move v1/v2/v3 packages with `git mv` to preserve history**

```bash
cd /Users/andrewbarry/projects/my-representatives/backend
git mv research/overview/v1 research/overview/legacy/v1
git mv research/overview/v2 research/overview/legacy/v2
git mv research/overview/v3 research/overview/legacy/v3
```

- [ ] **Step 3: Update `legacy/v1/pipeline.py` import**

In `backend/research/overview/legacy/v1/pipeline.py`, replace:

```python
from research.overview.v1.models import ResearchSummary
```

with:

```python
from research.overview.legacy.v1.models import ResearchSummary
```

- [ ] **Step 4: Update `legacy/v2/pipeline.py` imports**

In `backend/research/overview/legacy/v2/pipeline.py`, replace:

```python
from research.overview.v2.models import ResearchSummary
from research.overview.v2.synthesis_input import DossierResult, build_dossier
```

with:

```python
from research.overview.legacy.v2.models import ResearchSummary
from research.overview.legacy.v2.synthesis_input import DossierResult, build_dossier
```

(The `from research.overview._bullet_coercion import BulletList` line **stays the same** — `_bullet_coercion.py` is at top-level and shared.)

- [ ] **Step 5: Update `legacy/v2/synthesis_input.py` imports**

Inspect `backend/research/overview/legacy/v2/synthesis_input.py` for any `from research.overview.v2.` imports. Replace every occurrence of `research.overview.v2.` with `research.overview.legacy.v2.` using Edit's `replace_all=true`.

Run this to confirm none remain:

```bash
grep -n "research.overview.v2" /Users/andrewbarry/projects/my-representatives/backend/research/overview/legacy/v2/synthesis_input.py
```

Expected: no output.

- [ ] **Step 6: Update `legacy/v3/pipeline.py` imports**

In `backend/research/overview/legacy/v3/pipeline.py`, replace:

```python
from research.overview.v3.models import ResearchSummary
from research.overview.v3.prefilter import prefilter_results
```

with:

```python
from research.overview.legacy.v3.models import ResearchSummary
from research.overview.legacy.v3.prefilter import prefilter_results
```

- [ ] **Step 7: Update `legacy/v3/models.py` import**

`legacy/v3/models.py` imports `from research.overview._bullet_coercion import BulletList` — that line is fine, stays as-is (top-level). Verify no `research.overview.v3.` self-imports remain:

```bash
grep -n "research.overview.v3" /Users/andrewbarry/projects/my-representatives/backend/research/overview/legacy/v3/
```

Expected: no output.

- [ ] **Step 8: Update `__init__.py` dispatch to point at `legacy.*` for v1/v2/v3**

Replace `backend/research/overview/__init__.py` content with:

```python
"""Dispatch to the active rep overview pipeline version.

Default is ``v4`` (the flat top-level pipeline). The ``OVERVIEW_PIPELINE_VERSION``
env var (read at import time) can select a legacy variant for trace/cost
comparison: ``v1``, ``v2``, ``v3`` — all loaded from ``research.overview.legacy.*``.

Each selected version exports ``ResearchSummary``, ``research_representative``,
and ``TOTAL_SECTIONS`` from this module.
"""

import os

ACTIVE_VERSION = os.getenv("OVERVIEW_PIPELINE_VERSION", "v4")

if ACTIVE_VERSION == "v4":
    from .v4 import ResearchSummary, TOTAL_SECTIONS, research_representative
elif ACTIVE_VERSION == "v1":
    from .legacy.v1 import ResearchSummary, TOTAL_SECTIONS, research_representative
elif ACTIVE_VERSION == "v2":
    from .legacy.v2 import ResearchSummary, TOTAL_SECTIONS, research_representative
elif ACTIVE_VERSION == "v3":
    from .legacy.v3 import ResearchSummary, TOTAL_SECTIONS, research_representative
else:
    raise ValueError(
        f"Unknown OVERVIEW_PIPELINE_VERSION: {ACTIVE_VERSION!r}. "
        "Expected one of: v1, v2, v3, v4."
    )

__all__ = [
    "ACTIVE_VERSION",
    "ResearchSummary",
    "TOTAL_SECTIONS",
    "research_representative",
]
```

> Note: this still imports v4 from `.v4` — that's intentional. Task 2 flattens v4. Keeping the v4 import unchanged here means each task ends in a working tree.

- [ ] **Step 9: Verify imports succeed with default (v4) and each legacy value**

```bash
cd /Users/andrewbarry/projects/my-representatives/backend
conda activate my-reps
python -c "import os; os.environ.pop('OVERVIEW_PIPELINE_VERSION', None); from research.overview import ACTIVE_VERSION, ResearchSummary, TOTAL_SECTIONS, research_representative; print(ACTIVE_VERSION, TOTAL_SECTIONS)"
```

Expected output: `v4 1`

```bash
OVERVIEW_PIPELINE_VERSION=v1 python -c "from research.overview import ACTIVE_VERSION, TOTAL_SECTIONS; print(ACTIVE_VERSION, TOTAL_SECTIONS)"
```

Expected: `v1 5`

```bash
OVERVIEW_PIPELINE_VERSION=v2 python -c "from research.overview import ACTIVE_VERSION, TOTAL_SECTIONS; print(ACTIVE_VERSION, TOTAL_SECTIONS)"
```

Expected: `v2 1`

```bash
OVERVIEW_PIPELINE_VERSION=v3 python -c "from research.overview import ACTIVE_VERSION, TOTAL_SECTIONS; print(ACTIVE_VERSION, TOTAL_SECTIONS)"
```

Expected: `v3 1`

If any import fails with `ModuleNotFoundError: No module named 'research.overview.v1'` etc., it means a `legacy/vN/*.py` file still has an old internal import — re-grep and fix:

```bash
grep -rn "research\.overview\.v[123]" /Users/andrewbarry/projects/my-representatives/backend/research/overview/legacy/
```

Expected: no output.

- [ ] **Step 10: Commit**

```bash
cd /Users/andrewbarry/projects/my-representatives
git add backend/research/overview
git commit -m "$(cat <<'EOF'
refactor: move v1/v2/v3 overview pipelines into legacy/ subdir

v4 is the production default; v1/v2/v3 are kept available behind
OVERVIEW_PIPELINE_VERSION for comparison but live under legacy/ to
signal they are not the focus of further iteration. No behavior
change — env var contract, cache keys, trace names, and DB task_type
are all unchanged.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Flatten v4 to the top of `research/overview/`

With legacy moved, promote v4's modules out of `v4/` to the top level. After this task, `OVERVIEW_PIPELINE_VERSION=v4` (or unset) resolves to the flat top-level pipeline.

**Files:**
- Move (git mv): `backend/research/overview/v4/models.py` → `backend/research/overview/models.py`
- Move (git mv): `backend/research/overview/v4/state.py` → `backend/research/overview/state.py`
- Move (git mv): `backend/research/overview/v4/pipeline.py` → `backend/research/overview/pipeline.py`
- Move (git mv): `backend/research/overview/v4/nodes/` → `backend/research/overview/nodes/`
- Move (git mv): `backend/research/overview/v4/tools/` → `backend/research/overview/tools/`
- Move (git mv): `backend/research/overview/v4/prompts/` → `backend/research/overview/prompts/`
- Delete: `backend/research/overview/v4/__init__.py`
- Delete: `backend/research/overview/v4/` (now empty)
- Modify (8 Python files in moved tree): replace `research.overview.v4.` with `research.overview.` in every internal import
- Modify: `backend/research/overview/__init__.py` (dispatch for `v4` now points at flat top-level)

- [ ] **Step 1: Move v4 subdirs (nodes/, tools/, prompts/) to top level**

```bash
cd /Users/andrewbarry/projects/my-representatives/backend
git mv research/overview/v4/nodes research/overview/nodes
git mv research/overview/v4/tools research/overview/tools
git mv research/overview/v4/prompts research/overview/prompts
```

- [ ] **Step 2: Move v4 top-level modules**

```bash
cd /Users/andrewbarry/projects/my-representatives/backend
git mv research/overview/v4/models.py research/overview/models.py
git mv research/overview/v4/state.py research/overview/state.py
git mv research/overview/v4/pipeline.py research/overview/pipeline.py
```

- [ ] **Step 3: Remove the now-stale v4 `__init__.py` and empty directory**

```bash
cd /Users/andrewbarry/projects/my-representatives/backend
git rm research/overview/v4/__init__.py
rmdir research/overview/v4
```

If `rmdir` fails because something is left (e.g. `__pycache__`), inspect with `ls -la research/overview/v4` and remove leftovers before retrying.

- [ ] **Step 4: Rewrite internal v4 imports across the moved tree**

Every file moved from `v4/*` references `research.overview.v4.X` for its sibling modules. Update each:

In `backend/research/overview/pipeline.py`, replace these import lines:

```python
from research.overview.v4.models import ResearchSummary
from research.overview.v4.nodes.breadth_search import breadth_search
from research.overview.v4.nodes.filter_node import filter_node
from research.overview.v4.nodes.formatter import formatter
from research.overview.v4.nodes.query_generator import query_generator
from research.overview.v4.nodes.research_agent import research_agent_node
from research.overview.v4.state import V4State
```

with:

```python
from research.overview.models import ResearchSummary
from research.overview.nodes.breadth_search import breadth_search
from research.overview.nodes.filter_node import filter_node
from research.overview.nodes.formatter import formatter
from research.overview.nodes.query_generator import query_generator
from research.overview.nodes.research_agent import research_agent_node
from research.overview.state import V4State
```

In `backend/research/overview/state.py`, replace:

```python
from research.overview.v4.models import ResearchSummary, SearchResult
```

with:

```python
from research.overview.models import ResearchSummary, SearchResult
```

In `backend/research/overview/nodes/breadth_search.py`, replace:

```python
from research.overview.v4.models import SearchResult
from research.overview.v4.state import V4State
```

with:

```python
from research.overview.models import SearchResult
from research.overview.state import V4State
```

In `backend/research/overview/nodes/filter_node.py`, replace:

```python
from research.overview.v4.models import SearchResult
from research.overview.v4.state import V4State
```

with:

```python
from research.overview.models import SearchResult
from research.overview.state import V4State
```

In `backend/research/overview/nodes/query_generator.py`, replace:

```python
from research.overview.v4.state import V4State
```

with:

```python
from research.overview.state import V4State
```

In `backend/research/overview/nodes/formatter.py`, replace:

```python
from research.overview.v4.models import ResearchSummary, SearchResult, SourceLink
from research.overview.v4.state import V4State
```

with:

```python
from research.overview.models import ResearchSummary, SearchResult, SourceLink
from research.overview.state import V4State
```

In `backend/research/overview/nodes/research_agent.py`, replace:

```python
from research.overview.v4.models import SearchResult
from research.overview.v4.nodes.depth_subgraph import (
    DEPTH_RECURSION_LIMIT,
    build_depth_agent,
    build_depth_initial_user_message,
)
from research.overview.v4.state import V4State
```

with:

```python
from research.overview.models import SearchResult
from research.overview.nodes.depth_subgraph import (
    DEPTH_RECURSION_LIMIT,
    build_depth_agent,
    build_depth_initial_user_message,
)
from research.overview.state import V4State
```

In `backend/research/overview/nodes/depth_subgraph.py`, replace:

```python
from research.overview.v4.state import DepthState
from research.overview.v4.tools.tavily_search import depth_tavily_search
```

with:

```python
from research.overview.state import DepthState
from research.overview.tools.tavily_search import depth_tavily_search
```

In `backend/research/overview/tools/tavily_search.py`, replace:

```python
from research.overview.v4.models import SearchResult
```

with:

```python
from research.overview.models import SearchResult
```

- [ ] **Step 5: Verify no stale v4-prefixed imports remain in moved files**

```bash
grep -rn "research\.overview\.v4" /Users/andrewbarry/projects/my-representatives/backend/research/overview/
```

Expected: no output.

- [ ] **Step 6: Spot-check prompt path resolution still works after the move**

`nodes/formatter.py`, `nodes/query_generator.py`, `nodes/research_agent.py`, and `nodes/depth_subgraph.py` all derive prompt paths as `Path(__file__).resolve().parent.parent / "prompts"`. After the move, `parent.parent` resolves from `nodes/` to `overview/`, and `overview/prompts/` exists — so this keeps working without changes. Confirm by listing:

```bash
ls /Users/andrewbarry/projects/my-representatives/backend/research/overview/prompts/
```

Expected: 8 `.txt` files (query_gen_system, query_gen_user, research_agent_system, research_agent_user, depth_agent_system, depth_agent_user, formatter_system, formatter_user).

- [ ] **Step 7: Update top-level `__init__.py` so `v4` resolves to the flat top-level**

In `backend/research/overview/__init__.py`, change the v4 dispatch branch. Replace:

```python
if ACTIVE_VERSION == "v4":
    from .v4 import ResearchSummary, TOTAL_SECTIONS, research_representative
```

with:

```python
if ACTIVE_VERSION == "v4":
    from .models import ResearchSummary
    from .pipeline import research_representative
    TOTAL_SECTIONS = 1
```

`TOTAL_SECTIONS = 1` is inlined here because the previous `v4/__init__.py` (now deleted) was where the constant lived. Putting it in this module-level branch is sufficient — `from research.overview import TOTAL_SECTIONS` still works.

- [ ] **Step 8: Smoke-test imports for all four env var values**

```bash
cd /Users/andrewbarry/projects/my-representatives/backend
conda activate my-reps
python -c "import os; os.environ.pop('OVERVIEW_PIPELINE_VERSION', None); from research.overview import ACTIVE_VERSION, ResearchSummary, TOTAL_SECTIONS, research_representative; print(ACTIVE_VERSION, TOTAL_SECTIONS, ResearchSummary.__module__)"
```

Expected: `v4 1 research.overview.models`

```bash
OVERVIEW_PIPELINE_VERSION=v1 python -c "from research.overview import ACTIVE_VERSION, TOTAL_SECTIONS, ResearchSummary; print(ACTIVE_VERSION, TOTAL_SECTIONS, ResearchSummary.__module__)"
```

Expected: `v1 5 research.overview.legacy.v1.models`

```bash
OVERVIEW_PIPELINE_VERSION=v2 python -c "from research.overview import ACTIVE_VERSION, TOTAL_SECTIONS, ResearchSummary; print(ACTIVE_VERSION, TOTAL_SECTIONS, ResearchSummary.__module__)"
```

Expected: `v2 1 research.overview.legacy.v2.models`

```bash
OVERVIEW_PIPELINE_VERSION=v3 python -c "from research.overview import ACTIVE_VERSION, TOTAL_SECTIONS, ResearchSummary; print(ACTIVE_VERSION, TOTAL_SECTIONS, ResearchSummary.__module__)"
```

Expected: `v3 1 research.overview.legacy.v3.models`

If any import fails, re-run the `grep -rn "research\.overview\.v4"` check from Step 5 and fix stragglers.

- [ ] **Step 9: Smoke-test that the FastAPI app boots cleanly**

```bash
cd /Users/andrewbarry/projects/my-representatives/backend
conda activate my-reps
timeout 8 uvicorn main:app --port 8765 --host 127.0.0.1 2>&1 | head -40
```

Expected: log lines through "Uvicorn running on http://127.0.0.1:8765" (no `ImportError`, no `ModuleNotFoundError`). The `timeout 8` exit code 124 is expected — we just want to confirm it gets past import.

If any traceback appears, find the bad import and fix.

- [ ] **Step 10: Commit**

```bash
cd /Users/andrewbarry/projects/my-representatives
git add backend/research/overview
git commit -m "$(cat <<'EOF'
refactor: flatten v4 overview pipeline to research/overview/ top level

v4 was the only first-class pipeline; living under a v4/ subdir alongside
v1/v2/v3 underplayed that. Promote v4's modules (pipeline, models, state,
nodes/, tools/, prompts/) to the top-level package. OVERVIEW_PIPELINE_VERSION
defaults to v4 and resolves to the flat top-level; v1/v2/v3 stay reachable
via legacy.vN. Cache keys, trace names, env var names, and task_type strings
unchanged.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Update docs and frontend comments

Bring the prose in line with the new layout: v4 is the singular path forward, v1/v2/v3 are legacy. Touch every doc that talks about the version structure, plus two stale frontend comments.

**Files:**
- Modify: `/Users/andrewbarry/projects/my-representatives/CLAUDE.md`
- Modify: `/Users/andrewbarry/projects/my-representatives/README.md`
- Modify: `/Users/andrewbarry/projects/my-representatives/docs/DESIGN.md`
- Modify: `/Users/andrewbarry/projects/my-representatives/docs/INFRASTRUCTURE.md`
- Modify: `/Users/andrewbarry/projects/my-representatives/docs/rep-overview-versions.md`
- Modify: `/Users/andrewbarry/projects/my-representatives/docs/initiatives/V4_PERFORMANCE.md`
- Modify: `/Users/andrewbarry/projects/my-representatives/frontend/src/components/overview/bullets/types.ts`
- Modify: `/Users/andrewbarry/projects/my-representatives/frontend/src/components/overview/bullets/ResearchContent.tsx`

- [ ] **Step 1: Update CLAUDE.md — "Rep overview pipeline" section**

In `/Users/andrewbarry/projects/my-representatives/CLAUDE.md`, find the paragraph starting with `**Rep overview pipeline** lives in` (currently around line 59). Replace the **entire paragraph** (one long paragraph that ends with `…See \`docs/rep-overview-versions.md\` for the rationale behind each version.`) with:

```markdown
**Rep overview pipeline** lives in `research/overview/`. The production default is the flat top-level package (formerly known as "v4" — LangGraph breadth + adaptive depth + structured-output formatter). The `OVERVIEW_PIPELINE_VERSION` env var (read at import time) selects which pipeline runs; default is `v4`, which resolves to the flat top-level. Legacy variants `v1` / `v2` / `v3` are still selectable for trace/cost comparison and live under `research/overview/legacy/`. They are not the focus of further iteration. The dispatch module (`research/overview/__init__.py`) re-exports `ResearchSummary`, `research_representative`, and `TOTAL_SECTIONS` from whichever variant is active. **Each variant owns its own `ResearchSummary` Pydantic model** — there is no shared overview-model module. Bullet-shaped summaries (legacy v2, v3, and the current default) all define `ResearchSummary(bullets: list[str], citations: list[Citation])` with `bullets` as a required, non-nullable list (empty list = loading state). The previously-shared `list[str] | None` generated an `anyOf[array, null]` JSON schema that occasionally caused Anthropic to emit `bullets` as a JSON-encoded string — removing the null removed the ambiguity. All variants use LangChain + Langfuse tracing with version-prefixed `@observe` names (e.g. `v1-research-pipeline`, `v2-synthesis`, `v3-distill`, `v4-formatter` — the `v4-` prefix remains on the current default's trace names as a generation marker for Langfuse continuity) and a `UsageTracker` callback (`research/usage.py`) for token/tool-call accounting. See `docs/rep-overview-versions.md` for the rationale behind each version.
```

Then immediately below, replace the existing bullet list for v1/v2/v3/v4 (the four bullet items starting with `- **v1** (...)`, `- **v2** (...)`, `- **v3** (...)`, `- **v4** (...)`) with:

```markdown
- **Default** (`research/overview/`) — LangGraph-native breadth + adaptive depth. A top-level `StateGraph(V4State)` wires `query_generator → breadth_search → filter → research_agent → formatter`. **research_agent** is a structured-output triage call (not a react loop) — one LLM call returns a `_TriageOutput.depth_requests: list[_DepthRequest(topic, reason)]`, then those are dispatched concurrently via `asyncio.gather`; each spawns an isolated depth subagent. `OVERVIEW_V4_AGENT_MAX_DEPTH_CALLS` is a hard cap enforced in `research_agent.py`. (Earlier versions used `create_react_agent` here with a `request_depth_research` tool; rewritten 2026-04-30 — react steps were serial latency without buying better triage.) **Depth subagent** remains a `create_react_agent` over an isolated `DepthState`; its only tool, `depth_tavily_search`, returns `Command(update={search_results: [SearchResult], messages: [ToolMessage]})` so structured search results accumulate in `DepthState.search_results` while formatted snippets continue to drive the agent loop via `messages`. State isolation prevents the token-accumulation problem legacy v1/v2 suffered: a depth subagent's `messages` (Tavily ToolMessage snippets, agent reasoning) lives and dies in `DepthState` — only `SearchResult` lists cross back, tagged with the originating topic. **Formatter** takes `filtered_results` + `depth_search_results` (both `list[SearchResult]`, fully symmetric) and does curation+presentation in one structured-output call. Output schema is two **parallel top-level lists** indexed in lockstep — `bullet_texts: list[str]` and `bullet_sources: list[list[str]]` — never a nested `list[Bullet]`. The flat shape is what legacy v2/v3 use reliably; the original nested-list schema caused Sonnet 4.6 to stringify `bullets` as a JSON-encoded string in ~40% of runs (silent Pydantic validation failures, no user-visible output). The formatter wraps the structured-output call in LangChain's `with_retry(retry_if_exception_type=(ValidationError,), stop_after_attempt=2)` so any residual wire-shape miss gets one retry — empirically, the second attempt usually emits the correct shape. The user prompt ends with an explicit primacy/recency reminder of the wire shape (`bullet_texts` and `bullet_sources` must each be JSON arrays, not JSON-encoded strings). Citations are assembled in Python from `bullet_sources` (URL first-appearance order, deduped, looked up against the combined breadth+depth pool); URLs cited by the LLM but **not in the pool are silently dropped** in `_build_citations` (LLM hallucinates plausible URLs from training data; surfacing those would be a trust-breaker — drop count is logged for monitoring). `[N]` markers are appended to bullet text in Python — the LLM never emits markers, so there's no chance of N mismatch. **Bullet target: 6–8 bullets, ~14–22 words each** (set in `formatter_system.txt` + `formatter_user.txt`; see `docs/initiatives/V4_PERFORMANCE.md` for the iteration history that landed here). `TOTAL_SECTIONS=1`. Prompts in `research/overview/prompts/`. Tunable via `OVERVIEW_V4_*` env vars (see below) — the `V4_` env var prefix is preserved for deployment continuity.
- **Legacy `v1`** (`research/overview/legacy/v1/`) — 5 per-section research agents (policy_positions, recent_legislative_record, accomplishments, controversies, top_donors) run concurrently. Each uses a Tavily `web_search` tool, is capped at 5 searches / `recursion_limit=15`, and writes its result to `InMemoryResearchStore` as it completes, so the frontend streams sections in. Prompts in `research/overview/legacy/v1/prompts/`.
- **Legacy `v2`** (`research/overview/legacy/v2/`) — same 5 section agents, but results are fed into a dossier + unified citation pool and a single non-tool synthesis call produces 5–8 blended bullets with inline `[N]` markers. `TOTAL_SECTIONS=1` (store completes once at the end). Prompts in `research/overview/legacy/v2/prompts/`; dossier logic in `legacy/v2/synthesis_input.py`. Section agents' outputs are NOT user-facing — their prompts only ask for plain one-sentence findings with `[N]` markers (no markdown/headlines), since synthesis rewrites everything. Synthesis LLM emits only `bullets` via a private `_SynthesisBullets` schema; the unified citation list is assembled in Python from the dossier pool, not round-tripped through the model.
- **Legacy `v3`** (`research/overview/legacy/v3/`) — breadth-first retrieval: 1 LLM call generates ~15 queries, parallel Tavily fan-out (no LLM in the loop), `prefilter.py` dedupes/truncates, then one distillation call emits bullets + citations. `TOTAL_SECTIONS=1`. Prompts in `research/overview/legacy/v3/prompts/`. Tunable via `OVERVIEW_V3_*` env vars (see below). Distillation bullets *are* user-facing, so the distill prompt specifies the `**headline** - sentence [N]` display format.
```

- [ ] **Step 2: Update CLAUDE.md — "Cross-reference to the DB" paragraph**

In `/Users/andrewbarry/projects/my-representatives/CLAUDE.md`, find the line beginning with `**Cross-reference to the DB:**`. Replace it with:

```markdown
**Cross-reference to the DB:** `research_tasks.task_type` encodes the pipeline variant — `rep:v1` / `rep:v2` / `rep:v3` / `rep:v4` / `election` / `issue`. `rep:v4` is the current default; the other `rep:vN` rows come from legacy A/B runs. Use traces for "what happened in one run" and Postgres (`research_tasks`, `transactions`) for cross-run cost/token aggregates. The pipeline version came from the `OVERVIEW_PIPELINE_VERSION` env var at import time (default `v4`), so a trace's name prefix and its `task_type` suffix must agree — mismatches mean a bad deploy or env change mid-session.
```

- [ ] **Step 3: Update CLAUDE.md — `OVERVIEW_PIPELINE_VERSION` env var entry**

In `/Users/andrewbarry/projects/my-representatives/CLAUDE.md`, find the bullet `- \`OVERVIEW_PIPELINE_VERSION\` — which rep overview pipeline to run.`. Replace the entire bullet (one paragraph-long bullet) with:

```markdown
- `OVERVIEW_PIPELINE_VERSION` — selects which rep-overview pipeline to run. **Default `v4`** (the flat top-level pipeline at `research/overview/` — LangGraph breadth + adaptive depth). Legacy values `v1` (per-section streaming), `v2` (sections → synthesis bullets), `v3` (static-query fan-out → distill bullets) load from `research/overview/legacy/`. Read at import time by `research/overview/__init__.py`; encoded into `research_tasks.task_type` (`rep:v1`/`rep:v2`/`rep:v3`/`rep:v4`) and into Langfuse trace names. Prod sets `v4` explicitly on Cloud Run for visibility, but the code default is also `v4`.
```

- [ ] **Step 4: Update README.md — main paragraph + docs table**

In `/Users/andrewbarry/projects/my-representatives/README.md`, replace line 11 (the long sentence starting with `4. Click "Generate AI Research"…`) with:

```markdown
4. Click "Generate AI Research" on any rep — the active overview pipeline researches them. **Production runs the default top-level pipeline** at `research/overview/` (LangGraph breadth + adaptive depth subagent + formatter). Legacy variants `v1` (per-section streaming with skeletons), `v2`, and `v3` are kept under `research/overview/legacy/` for trace/cost comparison and are selectable via `OVERVIEW_PIPELINE_VERSION`. See [docs/rep-overview-versions.md](./docs/rep-overview-versions.md) for the full version history.
```

And replace line 12 (`5. v1 streams in section-by-section; v4 renders the full bullet block…`) with:

```markdown
5. The default pipeline renders the full bullet block once the formatter completes. Legacy `v1` streams in section-by-section. Results cached for 3 days.
```

In the docs table (around line 74), replace the row:

```markdown
| [rep-overview-versions.md](./docs/rep-overview-versions.md) | History and architecture of the v1/v2/v3/v4 rep overview pipelines |
```

with:

```markdown
| [rep-overview-versions.md](./docs/rep-overview-versions.md) | History and architecture of the default + legacy (v1/v2/v3) rep overview pipelines |
```

- [ ] **Step 5: Update docs/DESIGN.md — references to versions**

In `/Users/andrewbarry/projects/my-representatives/docs/DESIGN.md`:

Replace line 13 (starting with `4. When the user clicks "Learn More"…`) with:

```markdown
4. When the user clicks "Learn More" on a specific rep, the active overview research pipeline crawls the web to gather information about that representative. The default pipeline (LangGraph breadth + adaptive depth + formatter) lives at `backend/research/overview/`; legacy variants `v1` / `v2` / `v3` are kept under `backend/research/overview/legacy/` and selectable via `OVERVIEW_PIPELINE_VERSION`; see [rep-overview-versions.md](./rep-overview-versions.md) for the architecture of each.
```

Replace lines 15–16 (the two sub-bullets `- **v1**:` and `- **v2/v3**:`) with:

```markdown
   - **Default**: a single distilled bullet list renders once the formatter completes (no per-section streaming).
   - **Legacy `v1`**: results stream into the card section-by-section as each of 5 parallel agents completes. Sections are revealed in display order — a section stays as a skeleton placeholder until all preceding sections are complete, so the user always sees a clean top-down fill.
   - **Legacy `v2` / `v3`**: like the default — a single distilled bullet list once synthesis/distillation completes.
```

Replace line 38 (`The content in these cards is ultimately determined by the prompts…`) with:

```markdown
The content in these cards is ultimately determined by the prompts given to the active overview pipeline under [`backend/research/overview/`](../backend/research/overview/) and the Pydantic models used to structure the data. The default pipeline's prompts live in `research/overview/prompts/`; each legacy variant owns its own under `research/overview/legacy/vN/prompts/`.
```

Replace line 52 (`**v1 — five sections**…`) and line 62 (`**v2 / v3 — a single blended bullet list**…`) — the two paragraphs describing v1 vs v2/v3 output formats — with the parallel reframing. Find each and update so the prose reads as "Default", "Legacy v1", "Legacy v2 / v3" instead of bare "v1", "v2 / v3". Specifically:

Find:
```markdown
**v1 — five sections**, each a bulleted list with per-section citations:
```
Replace with:
```markdown
**Legacy `v1` — five sections**, each a bulleted list with per-section citations:
```

Find:
```markdown
**v2 / v3 — a single blended bullet list** (5–8 bullets) with a unified citation pool and inline `[N]` markers. V2 derives this from the same five section agents via a synthesis step; v3 derives it from a breadth-first search fan-out and a single distillation. See [rep-overview-versions.md](./rep-overview-versions.md).
```
Replace with:
```markdown
**Default and legacy `v2` / `v3` — a single blended bullet list** (6–8 bullets in the default, 5–8 in legacy) with a unified citation pool and inline `[N]` markers. The default derives this from a LangGraph breadth+depth flow; legacy `v2` from five section agents via a synthesis step; legacy `v3` from a breadth-first search fan-out and a single distillation. See [rep-overview-versions.md](./rep-overview-versions.md).
```

- [ ] **Step 6: Update docs/INFRASTRUCTURE.md — env var description**

In `/Users/andrewbarry/projects/my-representatives/docs/INFRASTRUCTURE.md`, replace line 61 (the `OVERVIEW_PIPELINE_VERSION` bullet) with:

```markdown
- `OVERVIEW_PIPELINE_VERSION` — which rep-overview pipeline to run. **Default `v4`** (the flat top-level pipeline at `research/overview/` — LangGraph breadth + adaptive depth). Set explicitly on Cloud Run rather than relying on the code default — makes the deployed version visible in the Cloud Run console. Other valid values: `v1` / `v2` / `v3` — these load legacy variants from `research/overview/legacy/`.
```

- [ ] **Step 7: Rewrite docs/rep-overview-versions.md**

In `/Users/andrewbarry/projects/my-representatives/docs/rep-overview-versions.md`, update the status table near the top. Replace lines 5–14 (the `## Current status (2026-05-01)` heading, the table, and the paragraph after) with:

```markdown
## Current status (2026-05-11)

| Variant | Status | UX | Code location |
|---------|--------|-----|---------------|
| **Default** (formerly "v4") | **Production** | Single-block bullet render once the formatter completes | `backend/research/overview/` |
| Legacy `v1` | Kept for comparison | Per-section streaming with skeletons (different paradigm — section headings appear immediately, fill in top-down as agents complete) | `backend/research/overview/legacy/v1/` |
| Legacy `v2` | Kept for comparison | Bullet block, like the default | `backend/research/overview/legacy/v2/` |
| Legacy `v3` | Kept for comparison | Bullet block, like the default | `backend/research/overview/legacy/v3/` |

The default pipeline does what legacy v2/v3 do but better — same single-block bullet UX, with adaptive depth on volatile claims and a more disciplined breadth/curation flow. Legacy variants are still importable behind `OVERVIEW_PIPELINE_VERSION` (`v1` / `v2` / `v3`) for trace/cost comparison, but they are not the focus of further iteration. The "v4" naming is preserved internally as a generation marker — env vars (`OVERVIEW_V4_*`), trace names (`v4-*`), and DB `task_type` strings (`rep:v4`) all keep the v4 prefix for deployment, analytics, and Langfuse continuity. Active tuning for the default pipeline lives in [`initiatives/V4_PERFORMANCE.md`](./initiatives/V4_PERFORMANCE.md).
```

In the same file, update the per-version section headers and code paths so they reflect the new layout:

Find:
```markdown
**Backend:** `research/overview/v1/pipeline.py`
**Frontend:** `components/overview/v1/ResearchContent.tsx`
**Prompts:** `research/overview/v1/prompts/`
```
Replace with:
```markdown
**Backend:** `research/overview/legacy/v1/pipeline.py`
**Frontend:** `components/overview/v1/ResearchContent.tsx`
**Prompts:** `research/overview/legacy/v1/prompts/`
```

Find:
```markdown
**Backend:** `research/overview/v2/pipeline.py`
**Frontend:** shares `components/overview/bullets/` with v3 (dispatched by response shape in `components/overview/index.tsx`)
**Prompts:** `research/overview/v2/prompts/` (5 section system/user prompts + `synthesis_system.txt` + `synthesis_user.txt`)
```
Replace with:
```markdown
**Backend:** `research/overview/legacy/v2/pipeline.py`
**Frontend:** shares `components/overview/bullets/` with legacy v3 and the default (dispatched by response shape in `components/overview/index.tsx`)
**Prompts:** `research/overview/legacy/v2/prompts/` (5 section system/user prompts + `synthesis_system.txt` + `synthesis_user.txt`)
```

Find:
```markdown
**Backend:** `research/overview/v3/pipeline.py` (+ `prefilter.py`)
**Frontend:** shares `components/overview/bullets/` with v2
**Prompts:** `research/overview/v3/prompts/` (`query_gen_system.txt`, `query_gen_user.txt`, `distill_system.txt`, `distill_user.txt`)
```
Replace with:
```markdown
**Backend:** `research/overview/legacy/v3/pipeline.py` (+ `prefilter.py`)
**Frontend:** shares `components/overview/bullets/` with legacy v2 and the default
**Prompts:** `research/overview/legacy/v3/prompts/` (`query_gen_system.txt`, `query_gen_user.txt`, `distill_system.txt`, `distill_user.txt`)
```

Find:
```markdown
**Backend:** `research/overview/v4/pipeline.py`
```
(this line shows up under the V4 section header). Replace with:
```markdown
**Backend:** `research/overview/pipeline.py` (the default pipeline, flat at the top level)
```

Find:
```markdown
**Prompts:** `research/overview/v4/prompts/` (`query_gen_*`, `research_agent_*`, `depth_agent_*`, `formatter_*`)
```
Replace with:
```markdown
**Prompts:** `research/overview/prompts/` (`query_gen_*`, `research_agent_*`, `depth_agent_*`, `formatter_*`)
```

- [ ] **Step 8: Update docs/initiatives/V4_PERFORMANCE.md — path references**

In `/Users/andrewbarry/projects/my-representatives/docs/initiatives/V4_PERFORMANCE.md`, search for any path that points at `research/overview/v4/`:

```bash
grep -n "research/overview/v4" /Users/andrewbarry/projects/my-representatives/docs/initiatives/V4_PERFORMANCE.md
```

For each match, replace `research/overview/v4/` with `research/overview/`. (For example, a phrase like `shipped 2026-05-01 in nodes/formatter.py + formatter_user.txt` doesn't need updates — those paths are already relative; only fully-qualified `research/overview/v4/...` paths get rewritten.) The doc's `v4-` trace names and `OVERVIEW_V4_*` env var references stay as-is — those are real, unchanged identifiers in code.

- [ ] **Step 9: Update frontend comment in `bullets/types.ts`**

In `/Users/andrewbarry/projects/my-representatives/frontend/src/components/overview/bullets/types.ts`, replace the JSDoc block at the top (around lines 1–10). Find:

```typescript
 * Shared rep overview schema for v2+ — a single blended bullet list
```

And replace the surrounding JSDoc to read:

```typescript
/**
 * Shared rep overview schema for the bullet-list UX (the default pipeline
 * and legacy v2/v3) — a single blended bullet list with a unified citation
 * pool and inline [N] markers.
 *
 * ``sources`` is populated by the default pipeline when ``OVERVIEW_V4_SHOW_SOURCES``
 * is on: a deduped breadth+depth pool projected to {title, url} entries, rendered
 * as an expandable "Further reading (N)" list below the bullets.
 */
```

(Preserve exactly what was there for the rest of the file — only the leading JSDoc paragraph is being rewritten.)

- [ ] **Step 10: Update frontend comment in `bullets/ResearchContent.tsx`**

In `/Users/andrewbarry/projects/my-representatives/frontend/src/components/overview/bullets/ResearchContent.tsx`, find the JSDoc block referring to v2/v3/v4. Replace lines 5–8 (the part that reads `currently v2, v3, v4` and `OVERVIEW_V4_SHOW_SOURCES`). Specifically replace:

```typescript
 * (currently v2, v3, v4). When v4 emits ``sources`` (gated on the
 * ``OVERVIEW_V4_SHOW_SOURCES`` backend flag), an expandable "Further reading (N)"
```

with:

```typescript
 * (the default pipeline plus legacy v2/v3). When the default pipeline emits
 * ``sources`` (gated on the ``OVERVIEW_V4_SHOW_SOURCES`` backend flag), an
 * expandable "Further reading (N)"
```

- [ ] **Step 11: Final scan for any stale `v4/` path references in docs**

```bash
grep -rn "research/overview/v4" /Users/andrewbarry/projects/my-representatives --include="*.md"
```

Expected: no output. Any remaining hit is a stale doc path — fix it inline by replacing `research/overview/v4/` with `research/overview/`.

```bash
grep -rn "research/overview/v[123]" /Users/andrewbarry/projects/my-representatives --include="*.md"
```

Expected: every hit should now be a `research/overview/legacy/vN/` path (or part of a code-block illustrating the old layout in a "history" context). Eyeball the output — if anything still says bare `research/overview/v1/` etc. in a sentence describing current-state code, fix it.

- [ ] **Step 12: Commit**

```bash
cd /Users/andrewbarry/projects/my-representatives
git add CLAUDE.md README.md docs frontend
git commit -m "$(cat <<'EOF'
docs: reflect overview pipeline restructure (v4 flat, v1-v3 legacy)

Update CLAUDE.md, README.md, DESIGN.md, INFRASTRUCTURE.md,
rep-overview-versions.md, V4_PERFORMANCE.md, and two frontend
comments to describe the new layout: default pipeline at the flat
top-level of research/overview/, legacy v1/v2/v3 under legacy/.
The v4-* trace name prefix, OVERVIEW_V4_* env vars, and rep:v4
task_type are preserved as a generation marker.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes

**Spec coverage:** Tasks 1–2 implement the file moves and import updates. Task 3 covers every doc/comment that mentions the version structure. No code paths were changed; behavior is identical for every value of `OVERVIEW_PIPELINE_VERSION`.

**Backwards-compat considerations:**
- `OVERVIEW_PIPELINE_VERSION` env var contract is preserved (same four valid values, same semantics for each).
- `OVERVIEW_V4_*` env vars are unchanged — production Cloud Run configs continue to work.
- `v4-*` Langfuse trace names are unchanged — historical Langfuse filters continue to work.
- `rep:v4` DB `task_type` is unchanged — analytics queries continue to work.
- `RepCache` keys version-tag with `ACTIVE_VERSION` (still `"v4"` for the default path) — existing cached entries remain valid.

**Risk:** Low. The whole change is mechanical file moves + path updates + docs. No new code, no schema changes, no behavior changes. The two end-of-task smoke tests cover all four `OVERVIEW_PIPELINE_VERSION` values.
