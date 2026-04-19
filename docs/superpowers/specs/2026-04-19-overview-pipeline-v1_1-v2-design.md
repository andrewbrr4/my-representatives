# Rep Overview Pipeline — v1.1 and v2 Design

**Date:** 2026-04-19
**Status:** Design approved, pending spec review
**Context:** See [docs/rep-overview-versions.md](../../rep-overview-versions.md) for the problem statement, v1 architecture, and the research that motivated these versions.

## Goal

Add two new overview pipeline versions that share an output contract and a common goal: produce a short, coherent, voter-useful overview instead of the current v1 wall of sections.

- **v1.1** uses the same 5 per-section agent structure as v1 as internal scaffolding, plus a final synthesis step that reconciles across sections and emits a tight blended overview.
- **v2** uses a breadth-first retrieval pipeline (query generation → parallel Tavily fan-out → distillation) that produces the same output contract.

Both versions must be selectable at deploy time via an env var so we can run them in the same codebase without per-request plumbing.

### Version isolation

Each version's directory is fully self-contained. **No version imports code or prompts from another version.** This means the v1.1 directory contains its own copy of the section-agent code and the 5 section prompts, even though they start identical to v1. The motivation is experimental freedom: editing v1.1 section prompts or agent logic must never affect v1 on main, and vice versa. Duplication is the accepted cost.

The only shared code lives under `research/overview/shared/` (currently just the `BulletsResearchSummary` output model, which is a schema contract rather than version-specific logic) and in modules already outside the version tree (`research/search.py`, `research/usage.py`, `store/`, `models.py`).

## Non-goals

- v2.1 (optional deep-dive agents for high-signal topics) is explicitly out of scope.
- Per-request version selection is out of scope (env var only).
- Redesigning v1's schema or deleting v1 is out of scope — v1 stays as-is.
- Frontend visual polish beyond "render the new bullet shape" is out of scope.

## Shared scaffolding

### Directory layout

```
backend/research/overview/
├── __init__.py            # dispatches based on OVERVIEW_PIPELINE_VERSION
├── shared/
│   ├── __init__.py
│   └── models.py          # BulletsResearchSummary (used by v1.1 and v2)
├── v1/                    # unchanged
├── v1_1/
│   ├── __init__.py        # re-exports ResearchSummary, research_representative
│   ├── pipeline.py        # own copy of section agent code + new synthesis step
│   └── prompts/
│       ├── policy_positions_system.txt         # copied from v1 at creation time
│       ├── policy_positions_user.txt
│       ├── recent_legislative_record_system.txt
│       ├── recent_legislative_record_user.txt
│       ├── accomplishments_system.txt
│       ├── accomplishments_user.txt
│       ├── controversies_system.txt
│       ├── controversies_user.txt
│       ├── top_donors_system.txt
│       ├── top_donors_user.txt
│       ├── synthesis_system.txt
│       └── synthesis_user.txt
└── v2/
    ├── __init__.py
    ├── pipeline.py
    └── prompts/
        ├── query_gen_system.txt
        ├── query_gen_user.txt
        ├── distill_system.txt
        └── distill_user.txt
```

### Version dispatch

`research/overview/__init__.py` reads `OVERVIEW_PIPELINE_VERSION` (`v1` | `v1_1` | `v2`, default `v1`) and re-exports `ResearchSummary` and `research_representative` from the active version's package. `backend/routers/overview.py` stays agnostic.

### Shared output schema

v1.1 and v2 both use `BulletsResearchSummary` (new, in `research/overview/shared/models.py`):

```python
class BulletsResearchSummary(BaseModel):
    bullets: list[str] | None = None     # 5–8 one-liners with inline [N] markers
    citations: list[Citation] = []        # unified, renumbered list
```

Each version re-exports it as `ResearchSummary` from its own `__init__.py` so the dispatch in `overview/__init__.py` works transparently.

v1's schema is unchanged. v1 remains the default until we flip the env var.

### Cache keying

`RepCache` keys are prefixed with the active version (e.g. `v1_1:<name>:<office>`). Switching versions naturally isolates cached results; no manual invalidation is required. Implementation touches `store/redis.py` and any other `RepCacheInterface` implementations.

### Research store

v1.1 and v2 both use `total_sections=1` — no progressive section streaming. The user sees a single loading state until the final bullets arrive. `InMemoryResearchStore` already supports this shape, so no store changes are needed beyond passing `total_sections=1` when creating tasks under v1.1/v2.

### Frontend

`RepCard.tsx` branches on response shape:

- If `bullets` field is present on the summary, render the tight-bullet overview with skeleton bullets during load.
- If `policy_positions` (etc.) is present, render the existing 5-section layout.

`types/index.ts` gets a discriminated union: `ResearchSummary = V1Summary | BulletsSummary`. No route or context changes.

## v1.1 — section agents + synthesis

### Flow (`research/overview/v1_1/pipeline.py`)

1. **Run 5 section agents.** v1.1 has its own copy of the section-agent code and the 5 section prompts (copied from v1 at creation time; thereafter edited independently). Run all 5 concurrently under v1.1's own semaphore. Each returns `(content, citations, usage)`. The code is structurally the same as v1's `run_section_agent` and `SECTIONS` but imports nothing from `research.overview.v1`.
2. **Assemble synthesis input.** Build a plain-text dossier for the synthesis step:
   ```
   ## policy_positions
   - <item> [1]
   - <item> [2]
   Sources: [1] <url> [2] <url>

   ## recent_legislative_record
   ...
   ```
   Build a stable renumbering map from `(section_name, original_index)` → unified index. The merged citation pool is the union of all section citations.
3. **Synthesis step.** One `ChatAnthropic` call — no tools, no agent loop — using `CLAUDE_MODEL` and `RESEARCH_MAX_TOKENS`. Structured output to `BulletsResearchSummary`. Prompt lives in `v1_1/prompts/synthesis_system.txt` and `synthesis_user.txt`. The prompt instructs the model to:
   - Produce 5–8 one-liner bullets blended across all topics.
   - Use inline `[N]` markers that reference citations from the provided pool only (no invented sources).
   - Resolve contradictions by preferring better-sourced claims.
   - Omit anything weakly supported.
4. **Write to store.** On success, call `store.complete_section(research_id, "overview", bullets, citations)`.

### Usage tracking

Each section agent keeps its own `UsageTracker` (as v1 does today). A new tracker wraps the synthesis call. All `UsageStats` sum into the final total returned to the router so DB cost rows capture section + synthesis input/output tokens and tool calls.

### Error handling

- Section agent failure: log and continue with empty content for that section (matches v1 today).
- Synthesis failure: fail the research task (user sees error state). No partial-fallback rendering since the UX is single loading state.

## v2 — breadth-first retrieval + distillation

### Flow (`research/overview/v2/pipeline.py`)

1. **Query generation.** One `ChatAnthropic` call (no tools, structured output) using `CLAUDE_MODEL`. Prompt asks for diverse queries spanning policy positions, votes, legislation sponsored, controversies, donors, local press, public statements, and biography. Returns `list[str]`. Prompts at `v2/prompts/query_gen_system.txt` + `query_gen_user.txt`.
2. **Parallel fan-out.** `asyncio.gather` N raw Tavily calls (no agent loop). An asyncio semaphore bounds concurrency to avoid hammering Tavily. Each query returns ~K results as `{title, url, snippet}`.
   - `OVERVIEW_V2_NUM_QUERIES` — default 15
   - `OVERVIEW_V2_RESULTS_PER_QUERY` — default 5
   - `OVERVIEW_V2_SEARCH_CONCURRENCY` — default 5
   - A raw-call helper is added to `research/search.py` alongside the existing agent-tool wrapper so both paths share HTTP and env plumbing.
3. **Pre-filter (no LLM).** Dedupe by URL (keep the highest-ranked occurrence), truncate snippets to a fixed character cap, and cap total results at a ceiling (default 60) to bound distillation input tokens.
4. **Distillation.** One `ChatAnthropic` call, no tools, structured output to `BulletsResearchSummary`. The prompt receives the filtered results plus the rep's name/office. Same output contract as v1.1: 5–8 blended one-liners with inline `[N]` markers drawn only from the provided URLs. The distillation step performs the citation renumbering. Prompts at `v2/prompts/distill_system.txt` + `distill_user.txt`.
5. **Write to store.** Single `complete_section` call on success.

### Usage tracking

Two trackers (query-gen, distillation). Tavily calls are summed into `UsageStats.tool_calls` manually (N queries = N tool calls) so DB cost rows capture Tavily spend correctly under the existing cost-config plumbing.

### Error handling

- Query-gen failure → fail the task.
- Individual search failure → log and skip; proceed with remaining results.
- Zero search results across all queries → fail the task.
- Distillation failure → fail the task.

### Cost note

v2 with defaults fires 15 Tavily calls per rep vs v1's ~25 (5 agents × up to 5 each), so v2 should be cheaper on search. Distillation input tokens will be higher than any single v1 section call because all snippets arrive in one prompt. Net cost is expected to favor v2 but should be measured via the existing `research_tasks` table once deployed.

## Configuration summary

New env vars:

| Name | Default | Purpose |
|---|---|---|
| `OVERVIEW_PIPELINE_VERSION` | `v1` | Dispatch target in `overview/__init__.py` |
| `OVERVIEW_V2_NUM_QUERIES` | `15` | Number of diverse queries generated for v2 |
| `OVERVIEW_V2_RESULTS_PER_QUERY` | `5` | Tavily results per query for v2 |
| `OVERVIEW_V2_SEARCH_CONCURRENCY` | `5` | Max in-flight Tavily calls for v2 |
| `OVERVIEW_V2_RESULTS_CEILING` | `60` | Post-dedupe cap on results passed to distillation |

No existing env vars change meaning.

## Testing

- Manual: set `OVERVIEW_PIPELINE_VERSION=v1_1`, run backend, generate overview for a sample rep, confirm bullets + unified citations render in the UI. Repeat for `v2`. Confirm `v1` still works as default.
- DB: confirm `research_tasks` rows land with correct `task_type="rep"` and non-zero token/tool-call counts for both new versions.
- Cache: confirm version-prefixed keys isolate cached results across version flips.

## Open questions

None at design time. Any tuning of `OVERVIEW_V2_NUM_QUERIES` or snippet caps should follow from measured behavior once the pipeline is running.
