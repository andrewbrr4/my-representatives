# Rep Overview v4 — Design Spec

**Status:** approved, ready for implementation plan
**Date:** 2026-04-25
**Pipeline version:** v4
**Predecessors:** v1 (per-section agents), v2 (sections → synthesis), v3 (static-query fan-out → distill). See `docs/rep-overview-versions.md` for the full version history.

## Goals

Take v3's speed and token-efficiency posture (search outside the LLM loop) and add **optional adaptive depth** for volatile subtopics, using LangGraph state isolation to avoid the token-accumulation problem that made v1/v2 expensive.

Specific aims:

1. **Breadth-first, then optional depth** — the deep-research-product pattern. Most reps need only the breadth pass; a small number of subtopics (ongoing controversies, pending litigation, candidacy status, breaking news) need a focused refresh to avoid stale claims.
2. **Stale-information prevention** — the breadth pass alone can return outdated information for volatile topics. The depth pass exists specifically to refresh those.
3. **Validation-error elimination** — formatting is its own final node operating on already-typed, already-validated structured `Finding` objects. The formatter only emits display text + `[N]` markers; citations are assembled in Python (v2 stringify-bullets lesson).
4. **LangGraph as a learning vehicle** — implementation should exercise core LangGraph features (state schemas, reducers, conditional edges, subgraphs, `ToolNode`/ReAct, state isolation across subgraph boundaries). Code should read like a clean LangGraph demo.
5. **Node-level swappability** — each node is a single module exporting one function with a uniform signature. Variants can be added as sibling files and wired in by changing one import in `pipeline.py`.

## Non-goals

- No frontend changes. v4 emits the same `{bullets, citations}` shape as v2/v3, so `components/overview/index.tsx` already dispatches it correctly.
- No multi-hop reasoning beyond one level of depth. The research agent can request depth research; the depth agent cannot itself request further depth.
- No retry/fallback to v3. v4 is selected via `OVERVIEW_PIPELINE_VERSION=v4`; if it fails the existing failure-handling path applies.

## Architecture

### Graph topology

```
                       START
                         │
                         ▼
               ┌──────────────────┐
               │ query_generator  │  (LLM → list[str])
               └──────────────────┘
                         │
                         ▼
               ┌──────────────────┐
               │ breadth_search   │  (parallel Tavily, no LLM)
               └──────────────────┘
                         │
                         ▼
               ┌──────────────────┐
               │ filter           │  (dedupe + truncate + rank)
               └──────────────────┘
                         │
                         ▼
               ┌──────────────────┐         tool: request_depth_research
               │ research_agent   │ ───────────────┐
               │  (ReAct subgraph)│                │
               │                  │                ▼
               │                  │    ┌──────────────────┐
               │                  │    │ depth_subgraph   │
               │                  │    │ (per-topic ReAct,│
               │                  │    │  isolated state) │
               │                  │ ◄──┴──────────────────┘
               └──────────────────┘
                         │
                         ▼
               ┌──────────────────┐
               │ formatter        │  (structured output → ResearchSummary)
               └──────────────────┘
                         │
                         ▼
                        END
```

### State isolation (the architectural argument)

Three separate `TypedDict` state schemas, one per scope. The point: each subgraph runs against a fresh, narrow context window — it cannot accumulate the parent's snippets or sibling subagents' tool-call history.

```python
# v4/state.py

class V4State(TypedDict):
    rep: Representative
    queries: list[str]
    raw_results: Annotated[list[SearchResult], operator.add]   # parallel-merge reducer
    filtered_results: list[SearchResult]
    findings: list[Finding]
    summary: ResearchSummary | None

class ResearchAgentState(TypedDict):                            # research_agent subgraph
    rep: Representative
    filtered_results: list[SearchResult]
    messages: Annotated[list[BaseMessage], add_messages]
    findings: list[Finding]                                     # only this returns to parent

class DepthState(TypedDict):                                    # one depth subagent
    rep: Representative
    topic: str
    reason: str
    messages: Annotated[list[BaseMessage], add_messages]
    findings: list[Finding]                                     # only this returns to caller
```

**Boundary contract:**

- The research_agent subgraph runs entirely inside `ResearchAgentState`. The wrapper node `research_agent_node(state: V4State)` extracts `state["filtered_results"]`, builds an inner `ResearchAgentState`, invokes the compiled subgraph, and returns only `{"findings": result["findings"]}` to `V4State`. The agent's `messages` history never crosses the boundary.
- The depth subgraph runs entirely inside `DepthState`. The `request_depth_research` tool builds an inner `DepthState`, invokes the compiled subgraph, and returns a string summary of `findings` for the agent to read in its messages, while also appending the `Finding` objects to a ledger the wrapper picks up before returning to `V4State`.

### Reducers

`Annotated[list[X], operator.add]` tells LangGraph to merge concurrent writes by list-concatenation. Required only on fields written by parallel branches:

- `V4State.raw_results` — `breadth_search` fans out N parallel Tavily queries.
- `ResearchAgentState.messages` and `DepthState.messages` — use the prebuilt `add_messages` reducer (handles tool/AI/human message merging).

Sequential fields (`queries`, `filtered_results`, `summary`) need no reducer.

## Components

### 1. `query_generator`

```python
async def query_generator(state: V4State) -> dict
```

- One LLM call with `with_structured_output(_QueryList)`.
- Generates `OVERVIEW_V4_NUM_QUERIES` queries (default 18) covering breadth across background, voting record, policy, controversies, accomplishments, current news.
- No tools.
- Prompt: `prompts/query_gen_system.txt`.

### 2. `breadth_search`

```python
async def breadth_search(state: V4State) -> dict
```

- No LLM. Async fan-out of Tavily over `state["queries"]`.
- Bounded by `OVERVIEW_V4_SEARCH_CONCURRENCY` (default 5) and `OVERVIEW_V4_RESULTS_PER_QUERY` (default 5).
- Returns flat list of `SearchResult` (not deduped — that happens in `filter`).

### 3. `filter`

```python
async def filter_node(state: V4State) -> dict
```

- Default implementation is heuristic, no LLM:
  - Dedupe by URL.
  - Truncate snippet to `OVERVIEW_V4_SNIPPET_CHAR_CAP` chars (default 800).
  - Cap total to `OVERVIEW_V4_RESULTS_CEILING` (default 60).
- Designed as the cleanest swap point — an LLM-based variant (`filter_node_llm.py`) can replace the heuristic by changing one import.

### 4. `research_agent` (subgraph)

A compiled ReAct subgraph with one tool. Built via `StateGraph(ResearchAgentState)`, two nodes (`agent`, `tools`), conditional edge for tool-call routing.

- LLM bound to `[request_depth_research]`.
- Wrapper node `research_agent_node` invokes the compiled subgraph with `recursion_limit=12`.
- Bounded depth-call budget: `OVERVIEW_V4_AGENT_MAX_DEPTH_CALLS` (default 3), enforced via prompt and verified in the conditional edge.
- Prompt directive: extract findings as factual claims with citations; call `request_depth_research` only for volatile claims (controversies, pending litigation, candidacy status, breaking news).
- Returns: `{"findings": [...]}` to `V4State`.
- Prompt: `prompts/research_agent_system.txt`.

### 5. `depth_subgraph` (subgraph)

Same structural pattern as `research_agent` — `StateGraph(DepthState)`, `agent`/`tools` nodes, conditional edges.

- LLM bound to `[tavily_search]`.
- Bounded by `recursion_limit=OVERVIEW_V4_DEPTH_RECURSION_LIMIT` (default 8).
- Prompt directive: investigate one specific subtopic, prefer recent sources, return concise findings.
- Returns: `{"findings": [...]}` to the calling tool.
- Prompt: `prompts/depth_agent_system.txt`.

### 6. `request_depth_research` tool

The bridge between research_agent and depth_subgraph. Defined as a LangChain `@tool`:

```python
@tool
async def request_depth_research(topic: str, reason: str) -> str:
    """Run a focused depth investigation on a specific subtopic.
    Use only for volatile/time-sensitive claims (ongoing controversies,
    pending litigation, candidacy status, breaking news)."""
```

Implementation pattern:

- `rep` is plumbed in via LangGraph's `InjectedState` annotation (idiomatic) rather than a contextvar.
- Tool builds inner `DepthState`, invokes `depth_graph.ainvoke(...)`.
- Returns a string summary of findings for the agent to read; appends the structured `Finding` objects to a per-invocation ledger that `research_agent_node` collects before returning to `V4State`.

### 7. `formatter`

```python
async def formatter(state: V4State) -> dict
```

- One LLM call with `with_structured_output(_FormatterBullets)`.
- `_FormatterBullets` schema contains **only** bullet text with `[N]` markers — no citation list.
- Citation list is assembled in Python from `state["findings"][i].source_urls`, deduped and renumbered. The `[N]` markers in bullets are remapped to the unified citation indices.
- Output: `ResearchSummary(bullets=[...], citations=[...])`.
- Prompt: `prompts/formatter_system.txt`. Bullet format: `**headline** - sentence [N]`. 5–8 bullets. Hard caps force judgment over enumeration.

## Models (`v4/models.py`)

```python
class SearchResult(BaseModel):
    url: str
    title: str
    snippet: str
    published_date: str | None

class Finding(BaseModel):
    claim: str                       # one-sentence factual statement
    source_urls: list[str]
    topic: str                       # rough category (e.g. "policy", "record", "controversy")

class Citation(BaseModel):           # matches frontend BulletsResearchSummary contract
    n: int
    url: str
    title: str

class ResearchSummary(BaseModel):
    bullets: list[str]               # required, non-nullable (v2 stringify-bullets lesson)
    citations: list[Citation]
```

## Code organization

```
backend/research/overview/v4/
├── __init__.py             # exports ResearchSummary, research_representative, TOTAL_SECTIONS=1
├── pipeline.py             # builds & compiles main graph; entrypoint research_representative()
├── state.py                # V4State, ResearchAgentState, DepthState
├── models.py               # Pydantic: ResearchSummary, Finding, SearchResult, Citation
├── nodes/
│   ├── __init__.py
│   ├── query_generator.py
│   ├── breadth_search.py
│   ├── filter_node.py
│   ├── research_agent.py   # builds & exports compiled ReAct subgraph + wrapper node fn
│   ├── depth_subgraph.py   # builds & exports compiled depth subgraph
│   └── formatter.py
├── tools/
│   ├── __init__.py
│   ├── tavily_search.py    # async Tavily wrapper, used by breadth_search and depth agent
│   └── request_depth.py    # @tool that invokes depth_subgraph w/ isolated state
└── prompts/
    ├── query_gen_system.txt
    ├── research_agent_system.txt
    ├── depth_agent_system.txt
    └── formatter_system.txt
```

**Uniform node signature:** every file in `nodes/` exports `async def <name>(state) -> dict[str, Any]` returning a partial state update. To experiment with a variant, drop a sibling file (e.g. `query_generator_static.py`) and change one import in `pipeline.py`.

## Pipeline wiring

```python
# v4/pipeline.py
graph = (
    StateGraph(V4State)
      .add_node("query_generator", query_generator)
      .add_node("breadth_search", breadth_search)
      .add_node("filter", filter_node)
      .add_node("research_agent", research_agent_node)
      .add_node("formatter", formatter)
      .add_edge(START, "query_generator")
      .add_edge("query_generator", "breadth_search")
      .add_edge("breadth_search", "filter")
      .add_edge("filter", "research_agent")
      .add_edge("research_agent", "formatter")
      .add_edge("formatter", END)
      .compile()
)
```

`research_representative(rep, store, research_id)` wraps `graph.ainvoke(...)`:

- `@observe(name="v4-research-pipeline")` on the entrypoint; nested observes on each node (`v4-query-gen`, `v4-research-agent`, `v4-depth-agent`, `v4-formatter`).
- `UsageTracker` callback wired into every LLM invocation.
- Tavily calls counted into the same tracker.
- Persistence on completion: `save_research_task()` + `save_transactions()` with `task_type="rep:v4"`.
- Writes final `summary` into `InMemoryResearchStore` (`TOTAL_SECTIONS=1`, completes once at end).

## Contract

Same as v1/v2/v3, satisfied via `v4/__init__.py` re-exports:

- `ResearchSummary` (Pydantic, `{bullets: list[str], citations: list[Citation]}`)
- `research_representative(rep, store, research_id)` (async)
- `TOTAL_SECTIONS = 1`
- Wired into `research/overview/__init__.py`'s version dispatch via `OVERVIEW_PIPELINE_VERSION=v4`.

Frontend dispatches on response shape (`bullets` field present), so no frontend changes needed.

## Environment variables

New, all v4-prefixed for isolation from v3:

- `OVERVIEW_V4_NUM_QUERIES` — number of breadth queries (default 18)
- `OVERVIEW_V4_RESULTS_PER_QUERY` — Tavily results per query (default 5)
- `OVERVIEW_V4_SEARCH_CONCURRENCY` — max in-flight Tavily calls (default 5)
- `OVERVIEW_V4_RESULTS_CEILING` — cap on total results fed to filter output (default 60)
- `OVERVIEW_V4_SNIPPET_CHAR_CAP` — max chars per snippet (default 800)
- `OVERVIEW_V4_AGENT_MAX_DEPTH_CALLS` — max depth-research calls per pipeline run (default 3)
- `OVERVIEW_V4_DEPTH_RECURSION_LIMIT` — recursion limit per depth subagent (default 8)

## Observability

Trace-name taxonomy (Langfuse):

- `v4-research-pipeline` — top-level entrypoint
- `v4-query-gen` — query_generator
- `v4-research-agent` — research_agent subgraph entry
- `v4-depth-agent` — depth_subgraph entry (one span per depth call)
- `v4-formatter` — formatter

`research_tasks.task_type = "rep:v4"`. The trace-name prefix and `task_type` suffix must agree (mismatch indicates a bad deploy or env change mid-session).

## Tradeoffs and open risks

- **Latency floor higher than v3.** v3 is ~2 LLM calls (query_gen + distill). v4 is at minimum ~3 (query_gen + research_agent + formatter), more if the agent calls depth. Acceptable given depth is opt-in per claim and the formatter is small.
- **Agent recursion in research_agent.** Even with state isolation across subgraphs, the research_agent's own ReAct loop can spiral. Mitigation: hard cap via `recursion_limit=12` and budget cap via prompt + conditional-edge check.
- **Depth-trigger quality depends on prompt.** Whether the agent correctly identifies volatile claims is a prompt-engineering question, not an architecture question. Tune via prompt iteration after first runs.
- **Citation deduplication.** When findings come from both breadth and depth, the same URL may appear under multiple findings. Dedup by URL when building the citation list, but preserve all `[N]` markers correctly mapped.

## Version-history doc update

After v4 ships, append a v4 section to `docs/rep-overview-versions.md` matching the format of v1/v2/v3 (architecture, what it fixes, tradeoffs).
