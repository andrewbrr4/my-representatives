# Rep Overview Pipeline — Version History & Research

Living document tracking the evolution of the representative overview research pipeline.

## The Core Problem

When a user clicks "Generate AI Overview" for a representative, the system needs to:
1. **Retrieve** broad, current information about the rep from the web
2. **Present** that information in a concise, coherent, voter-useful format

These are in tension: broad retrieval requires many web searches, which produces large amounts of raw data that must be synthesized coherently without blowing up LLM context windows or token costs.

---

## V1: Per-Section Agents (current)

**Architecture:** 5 independent LangChain agents run in parallel, each focused on one section (policy positions, legislative record, accomplishments, controversies, top donors). Each agent has a Tavily `web_search` tool and produces structured output (bullet points + per-section citations).

**Backend:** `research/overview/v1/pipeline.py`
**Frontend:** `components/overview/v1/ResearchContent.tsx`
**Prompts:** `research/overview/v1/prompts/`

**How it works:**
- Each section agent gets its own system + user prompt
- Each agent independently searches the web (up to 5 searches, recursion_limit=15)
- Results stream to the frontend as each agent completes (incremental rendering)
- Frontend renders sections top-down, showing skeletons until preceding sections finish

**Known problems:**
1. **Sections contradict each other** — each agent searches independently, so findings in one section can conflict with another, and neither agent knows
2. **Uneven information quality** — agents don't always surface the most important/current issues a politically-aware voter would expect
3. **Too much text** — 5 sections of 3-5 bullet points each produces a wall of content that real users' eyes glaze over
4. **No cross-section awareness** — agents can't prioritize globally (e.g., if there's a major ongoing story, it should dominate the overview, but each agent treats its section as equally important)

**Why this architecture was chosen (context from earlier iteration):**
A previous single-agent approach blew up input tokens. The agent loop pattern means every Tavily search result (title + URL + content snippet, 5 results per search) accumulates in the agent's conversation history. After 15+ searches, the agent re-reads 75+ snippets on every subsequent LLM call. Input tokens maxed out, so the codebase pivoted to per-section agents with limited scope.

---

## The Fundamental Tension

- **Broad unified research** = one agent doing many searches = search results accumulate in the agent's conversation context = input tokens explode
- **Narrow scoped research** = multiple agents with small context = manageable tokens but contradictions, gaps, and incoherence

This is a context window management problem, not just a pipeline architecture problem.

---

## Research: Approaches for V2+

Findings from research sessions exploring alternative architectures.

### Recommended direction: Search Outside the LLM Loop

For a representative overview — not open-ended research — you don't need adaptive search. You know upfront what you're looking for. Adaptive search (where finding X leads you to search for Y) adds complexity and token cost without much marginal benefit here.

**Proposed 2-stage pipeline:**
1. **Information retrieval** — gather all raw information with citations, focused on breadth
2. **Presentation** — separate step that synthesizes and formats for the user

### Option A: Static Query Generation + Parallel Search + Single Synthesis

1. One LLM call generates 12-18 targeted search queries
2. Execute all Tavily searches in parallel (no LLM in the loop)
3. Preprocessing: deduplicate by URL, truncate snippets, score/rank by recency
4. Single synthesis LLM call with all results

**Token math:** Tavily returns ~200-word snippets. At 5 results per query x 15 queries = 75 snippets x ~250 tokens = ~18-20K tokens input for synthesis. Well within context limits for a single call, and no accumulation since there's no agent loop.

### Option B: Map-Reduce (if Option A's synthesis input is too large)

Same as A for query generation + parallel search, but add a "map" step: for each search result batch, a small LLM call extracts key facts into bullet points. Then a "reduce" step synthesizes the extracted facts. Caps synthesis input regardless of search count.

### Option C: Agent Loop with Compression (not recommended)

Keep the agent pattern but periodically checkpoint — summarize findings, start fresh context with just the summary. Lossy at each compression step and complex. Skip it.

### Hybrid Enhancement: Pre-structured Query Templates

Instead of generating queries cold, maintain a template library:
```
QUERY_TEMPLATES = {
  "policy": ["{name} policy positions {year}", "{name} voting record"],
  "donors": ["{name} campaign finance FEC", "{name} top donors opensecrets"],
  "controversy": ["{name} controversy criticism", "{name} ethics investigation"],
  ...
}
```
Let a small LLM call select and customize from templates rather than generate from scratch. Consistent coverage, deduplication by URL.

### Enhancement: Source-Type Routing

Some queries are better served by specific sources: OpenSecrets for donor data, Congress.gov/GovTrack for voting records, Ballotpedia for biographical/position summaries. Hit these directly rather than through Tavily for structured data types.

### Enhancement: Cross-Reference / Contradiction Check

After synthesis, one cheap LLM call specifically tasked with finding contradictions in the draft output. Addresses coherence without requiring unified search.

### Output Format Considerations

The 5-section bullet list is the wrong primitive. Bullets encourage exhaustive listing; voters want judgment.

Proposed "what do I actually need to know" format:
- **One-liner:** What this person is primarily known for, one sentence
- **Key positions (3 max):** Their stances on the 3 most salient current issues
- **Recent record:** 2-3 notable actions/votes in the last 2 years
- **Watch out for (optional):** 1-2 things a critical voter should know. Omit if nothing significant.
- **Top funder category:** Not a list — "primarily funded by [category]" with top donor named
- **4-6 inline citations** total, not 40

Key design decisions: hard caps force the LLM to exercise judgment rather than enumerate. Optional sections avoid false balance. Minimize citation count to the actually important ones.

### How Deep Research Products Handle This

Patterns from Perplexity Deep Research, Gemini Deep Research, etc.:
- **Breadth-first then depth-first:** Wide search identifies important subtopics, focused searches go deep on those
- **Chunked context with working memory:** "Working notes" scratchpad that's periodically compressed, rather than accumulating raw snippets
- **Result scoring before synthesis:** Rank by recency + relevance before feeding to LLM, cutting synthesis input significantly

---

## Version Swapping

### Backend
Change one line in `research/overview/__init__.py`:
```python
# from .v1 import ResearchSummary, research_representative
from .v2 import ResearchSummary, research_representative
```

### Frontend
Change one line in `components/overview/index.ts`:
```typescript
// export { ResearchContent } from "./v1";
export { ResearchContent } from "./v2";
```

Each version must export:
- **Backend:** `ResearchSummary` (Pydantic model) + `research_representative(rep, store, research_id)` (async function)
- **Frontend:** `ResearchContent` (React component taking `{ summary }`) + `ResearchSummary` (TypeScript interface)
