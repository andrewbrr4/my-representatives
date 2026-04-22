---
name: langfuse-trace-debugging
description: Use this FIRST when debugging LLM/agent issues in Langfuse-instrumented apps — recursion limits, unexpected tool loops, failures, cost/token spikes, latency regressions, agents returning empty results, or any "what is the agent actually doing" investigation. Works with LangChain, LangGraph, and direct Anthropic/OpenAI calls. Trigger whenever the user mentions traces, spans, observations, Langfuse, @observe decorators, trace names, callbacks, recursion_limit, tool call loops, or wants to inspect why an agent behaved a certain way. Use even when the user seems to know the answer — trace evidence often contradicts code-reading hypotheses. Skip ONLY if the app has no Langfuse integration or the user explicitly wants code analysis only.
---

# Langfuse Trace Debugging

## Why this exists

When an LLM app misbehaves, the cheapest diagnostic is *what it actually did*, not *what the code looks like*. Langfuse traces are the authoritative record. Reading code to form hypotheses without first checking traces leads to confident-sounding wrong answers — the agent hit the recursion limit on the 7th search, or it never called the tool at all, or the structured_response was valid but empty, and none of that is visible in the source.

**Iron law:** If the app is Langfuse-instrumented, pull trace evidence *before* reading implementation code. Use code to interpret the evidence, not to guess at it.

## The Langfuse MCP toolset

The MCP surfaces six tools that matter for debugging. Know what each is for; pick the cheapest one that answers your question.

| Tool | Best for | Cost |
|------|----------|------|
| `get_error_count(age)` | "How bad is it?" — scope check before investigation | Cheap |
| `find_exceptions(age, group_by)` | Locate hotspots by file / function / exception type | Cheap |
| `fetch_traces(age, name?, tags?, metadata?)` | Find the right trace(s) by name pattern or tag | Medium |
| `fetch_trace(trace_id, include_observations=True)` | Full timeline of one trace: LLM calls, tool calls, tokens, timings | Medium |
| `fetch_observations(age, type, name?, trace_id?)` | Narrow slice — e.g. only SPANs named `*-section-agent` | Medium |
| `get_exception_details(trace_id)` | Stack + message for a specific failure | Cheap given trace_id |

`age` is in minutes (max 10080 = 7 days). Default to the narrowest window you can justify — 60–240 min for an active investigation.

## The workflow

### 1. Scope

Before pulling a single trace, ask what you're actually investigating. "Recursion limits in v2 section agents" and "v2 is slow" need different queries. Decide:

- **Is it an exception, or wrong-but-successful output?** Exception → start with `find_exceptions` / `get_error_count`. Wrong output → go straight to `fetch_traces` on the affected trace name.
- **What time window?** If the user said "just now," use 60 min. If they said "today," 1440. Wider windows are slower and noisier.
- **What's the trace name?** Langfuse traces are usually named via `@observe(name=...)` or LangChain's `run_name`. Find this in the code if the user hasn't said it — grep for `@observe` or `run_name=`. In this project see `CLAUDE.md` under "Debugging with Langfuse" for the trace-name taxonomy.

### 2. Find the right trace(s)

Prefer `fetch_traces` with a `name` filter over a blind time-range query. Example queries by investigation type:

**A specific failure mode (exceptions):**
```
find_exceptions(age=240, group_by="function")  # where is it breaking?
fetch_traces(age=240, tags="error")            # if tagged
```

**A specific pipeline version behaved oddly:**
```
fetch_traces(age=120, name="v2-section-agent")     # LangChain run_name
fetch_traces(age=120, name="v2-research-pipeline") # top-level @observe
```

**One known bad run (user gave you a trace_id or timestamp):**
```
fetch_trace(trace_id="...", include_observations=True)
```

`fetch_traces` returns a list with IDs + summaries; pick 2–3 representative ones before deep-diving. Don't load all 50.

### 3. Open the trace with observations

```
fetch_trace(trace_id=<id>, include_observations=True, output_mode="compact")
```

`include_observations=True` is the whole point — without it you get the trace shell but not the LLM/tool calls inside. The compact mode is usually enough; use `full_json_file` only when you need to grep the raw payloads (e.g. exact system prompts).

### 4. Read the trace like a timeline

Observations come in three types. Read them in chronological order and look for:

- **GENERATION** (LLM calls): input messages, output, model, prompt+completion tokens, latency. Red flags: empty output, truncated output (completion_tokens equals max_tokens), model isn't what you expected, unexpectedly high input_tokens (bloated context).
- **SPAN** (non-LLM work, tool calls, sub-functions): name, input, output, duration. Red flags: tool called many more times than expected (recursion smell), tool errored and the agent didn't recover, structured output validation failed silently.
- **EVENT** (discrete log points): less common; check for custom error events.

For **recursion-limit issues specifically**: count the GENERATION + tool SPAN alternations inside the agent observation. LangChain/LangGraph stops at `recursion_limit`; if you see N tool calls and the next generation is empty/partial, the agent ran out of budget. Cross-check against the `recursion_limit` in code.

For **token/cost spikes**: sum `prompt_tokens` across GENERATIONs in the trace. A single ballooning input (e.g. accumulated tool results, unbounded context) usually shows up as one GENERATION with input_tokens far above the rest.

For **silent failures** (agent returned empty result, no exception): look at the final GENERATION's output and the `structured_response` extraction — Pydantic validation errors often become empty objects rather than exceptions, depending on how the agent wraps them.

### 5. Confirm with code — last, not first

Now open the implementation. You know which span failed, at what step, with what input. Read *that specific function* to understand why the observed behavior happened. This is the step where you formulate a fix.

## Anti-patterns

- **Grepping code before pulling a trace.** You're guessing. Stop.
- **`fetch_traces` with no `name` filter on a large window.** You get a flood; pick a name.
- **Calling `fetch_trace` without `include_observations=True`.** The interesting stuff is in observations.
- **Assuming one bad trace is representative.** Pull 2–3 of the same name before concluding. Flaky behavior has different shapes per run.
- **Declaring the bug fixed without a re-run trace.** After the fix, run the scenario again and fetch the new trace. Evidence before assertions.

## Handing off

When reporting findings to the user, include the `trace_id` and a one-line pointer like: "Trace `abc123` shows the v2 policy_positions agent made 14 search calls before hitting recursion_limit=15 — raising the cap or capping search breadth per section will fix it." A `trace_id` lets them verify in the Langfuse UI.

## Related

- If the app has a separate DB table for cost/usage (this project has `research_tasks` + `transactions`), traces answer "what happened" and the DB answers "how much did it cost across N runs." Use both when tuning cost regressions.
- For systematic debugging discipline around the evidence you gather, pair this with `superpowers:systematic-debugging`.
