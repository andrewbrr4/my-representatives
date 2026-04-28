# V4 Research Agent — Detailed Flow

Walk-through of how data and control flow through the v4 research_agent, depth subagent, and formatter, from the moment we arrive with filtered breadth-first search results to the moment the user-facing bullets + citations are assembled.

## 1. Entry: top-level graph routes here

`pipeline.py:41` — the edge `filter → research_agent` fires after `filter_node` populates `V4State["filtered_results"]`. The graph invokes the registered node function, which is `research_agent_node` (`pipeline.py:36`).

## 2. The research_agent wrapper — V4State scope

`research_agent.py:48-106` — `research_agent_node(state: V4State)` runs in the parent's scope. Three things happen here:

### a. Per-run setup (`research_agent.py:55-81`)

```python
rep = state["rep"]
filtered_results = state.get("filtered_results") or []
# system + user prompts substituted from .txt templates
request_depth_tool = make_request_depth_tool(rep)
model = ChatAnthropic(...)
agent = create_react_agent(
    model,
    tools=[request_depth_tool],
    state_schema=ResearchAgentState,
    prompt=system_prompt,
)
```

The depth tool is built **per run** because `rep` is closure-captured (`request_depth.py:38-104`) — that's how the depth tool knows who it's researching without exposing `rep` to the LLM. The agent itself is a LangGraph prebuilt (`create_react_agent`), so we don't hand-roll the agent ↔ tools loop. The custom `state_schema=ResearchAgentState` (extends `langgraph.prebuilt.chat_agent_executor.AgentState`) gives us the extra channels: `rep`, `filtered_results`, and `depth_search_results` (the accumulator the tool writes into via `Command(update=...)`).

### b. State projection (`research_agent.py:86-91`)

```python
initial: ResearchAgentState = {
    "messages": [HumanMessage(content=user_prompt)],
    "rep": rep,
    "filtered_results": filtered_results,
    "depth_search_results": [],
}
```

Only the fields the agent needs are passed in. `queries`, `raw_results`, `usage_log`, `summary` from `V4State` do NOT cross — see `state.py:25-37` vs `state.py:40-54`. The breadth results enter the LLM context exactly once, as part of the seed `HumanMessage`.

### c. Agent invoke (`research_agent.py:92-99`)

```python
result = await agent.ainvoke(
    initial,
    config={
        "callbacks": [langfuse_handler, usage_tracker],
        "recursion_limit": _AGENT_RECURSION_LIMIT,  # 12
        "run_name": f"v4:research-agent:{rep.name}",
    },
)
```

---

## 3. Inside the research_agent — ReAct loop (prebuilt)

`create_react_agent` runs the standard `agent → tools → agent → ... → END` loop. We didn't write any of that — it's the LangGraph prebuilt.

### 3a. The agent decides whether to call depth

The system prompt (`prompts/research_agent_system.txt`) restricts depth calls to volatile/time-sensitive claims (controversies, pending litigation, candidacy status, breaking news), capped at `_MAX_DEPTH_CALLS` (`research_agent.py:32`). The user prompt (`prompts/research_agent_user.txt`) carries the breadth results block.

If the agent emits no `tool_calls`, the loop ends. If it emits a `request_depth_research` call, control goes to the prebuilt's tools node.

### 3b. Tool call: `request_depth_research`

`request_depth.py:42-103`. Builds a fresh depth subagent (a `create_react_agent` over `DepthState`) and invokes it:

```python
depth_agent = build_depth_agent()
result = await depth_agent.ainvoke(
    {"rep": rep, "topic": topic, "reason": reason,
     "search_results": [],
     "messages": [build_depth_initial_user_message({...})]},
    config={"recursion_limit": DEPTH_RECURSION_LIMIT},  # 8
)
```

---

## 4. The depth subagent — also a `create_react_agent`

`depth_subgraph.py:31-49` — same prebuilt pattern as research_agent, but:

- Custom `state_schema=DepthState` (extends `AgentState` with `rep`, `topic`, `reason`, `search_results`).
- Single tool: `depth_tavily_search` (`tools/tavily_search.py:36-65`).

### 4a. The depth Tavily tool

`depth_tavily_search` is a `@tool` that returns `Command(update=...)`:

```python
return Command(
    update={
        "search_results": results,                              # SearchResult list
        "messages": [ToolMessage(content=formatted, ...)],      # for the next agent turn
    }
)
```

This is the key trick of the new design: **structured `SearchResult` objects accumulate in `DepthState.search_results` (via reducer) while the formatted snippet block goes back to the LLM as a normal `ToolMessage`** so the next agent turn can reason over what was found. One tool call writes to two channels.

### 4b. Depth agent loop

The depth agent runs Tavily searches until it stops calling tools (prompt-budgeted to ~4 searches per topic). When it ends, control returns to `request_depth_research`.

### 4c. Findings flow back to research_agent state

Back in `request_depth_research` (`request_depth.py:84-103`):

```python
depth_results = result.get("search_results") or []
# Tag each result with the depth topic at the boundary
tagged = [SearchResult(..., topic=topic) for r in depth_results]
return Command(
    update={
        "depth_search_results": tagged,
        "messages": [ToolMessage(content=ack, tool_call_id=tool_call_id)],
    }
)
```

Two things land in `ResearchAgentState`:

- `depth_search_results` gets the tagged `SearchResult` list. The reducer `operator.add` on `state.py:53` accumulates across multiple depth calls.
- `messages` gets a short ack `ToolMessage` — titles + URLs only, NOT the full snippet content. That's the second state-isolation boundary: the depth Tavily ToolMessage transcripts never enter research_agent's context.

### 4d. Loop continues

The prebuilt routes back to the agent node. Agent sees the ack, decides whether to call depth again (capped by prompt-enforced budget) or stop.

---

## 5. Research_agent ends → wrapper returns to V4State

When the agent emits no more `tool_calls`, the prebuilt routes to END. Result returns to the wrapper.

The wrapper extracts only `depth_search_results` and projects back to V4State (`research_agent.py:101-106`):

```python
depth_search_results = result.get("depth_search_results") or []
return {"depth_search_results": depth_search_results, "usage_log": [usage_tracker.stats]}
```

**This is the third boundary.** `messages`, the per-run agent, the closure-captured tool — all dropped at the wrapper. Only `depth_search_results` and a `UsageStats` enter V4State.

---

## 6. Formatter — curation + presentation in one call

`pipeline.py:42` — edge `research_agent → formatter`.

`formatter.py:120-160` — the formatter receives `filtered_results` (the breadth pool) and `depth_search_results` (depth pool, tagged by topic). Both blocks are rendered into the prompt; the depth block groups results by topic so the formatter can label them. One LLM call with `with_structured_output(_FormatterOutput)`.

Schema (`formatter.py:33-44`):

```python
class _Bullet(BaseModel):
    text: str           # bare one-liner, NO [N] markers
    source_urls: list[str]   # URLs supporting this bullet

class _FormatterOutput(BaseModel):
    bullets: list[_Bullet]
```

Once the LLM returns:

1. **Citation list assembly** (`formatter.py:80-110`) — iterate `bullets[*].source_urls` in order, dedupe, look up title/published-date metadata in the **combined breadth+depth pool** (so depth-only URLs get real metadata too). Returns `(citations, url_to_n)` where `url_to_n` is a 1-indexed map.
2. **Marker attachment** (`formatter.py:113-121`) — for each bullet, look up its source URLs in `url_to_n`, sort the resulting Ns, and append `[N1][N2]...` to the bullet text.
3. Final `ResearchSummary(bullets=bullet_texts, citations=citations)` returned to V4State (`formatter.py:160`).

**Why python builds the markers**: the LLM only knows the URLs it cites, not their assigned N. Building `url_to_n` after-the-fact in python and rendering markers there means the bullets and the citation list can never disagree.

---

## Boundary summary

| Boundary | Entered with | Returned with |
|---|---|---|
| V4State → ResearchAgentState (`research_agent.py:86-99`) | `rep`, `filtered_results`, seed user message | `depth_search_results`, `usage_log` |
| ResearchAgentState → DepthState (via tool, `request_depth.py:62-72`) | `rep`, `topic`, `reason`, seed user message | `search_results` (tagged with topic, surfaced as `depth_search_results` in parent) + short ack `ToolMessage` |
| Inside ResearchAgentState | full `messages` history, `depth_search_results` accumulator | (stays inside) |
| Inside DepthState | full Tavily `ToolMessage` transcript | (stays inside; only `search_results` cross out) |

Three nested state scopes, with explicit projection at each boundary. The depth subagent's Tavily snippet pile never reaches the formatter, the research_agent's ReAct messages never reach V4State, and the inputs to the formatter (breadth + depth) are now fully symmetric `list[SearchResult]`.
