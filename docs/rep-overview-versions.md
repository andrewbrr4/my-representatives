# Rep Overview Pipeline — Version History & Research

Living document tracking the evolution of the representative overview research pipeline.

## The Core Problem

When a user clicks "Generate AI Overview" for a representative, the system needs to:
1. **Retrieve** broad, current information about the rep from the web
2. **Present** that information in a concise, coherent, voter-useful format

These are in tension: broad retrieval requires many web searches, which produces large amounts of raw data that must be synthesized coherently without blowing up LLM context windows or token costs.

---

## V1: Per-Section Agents (default)

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

---

## V2: Sections → Synthesis Bullets

**Architecture:** Same 5 section agents as v1, but their outputs are no longer delivered straight to the user. Instead, they feed a second-stage synthesis call that collapses the dossier into a single blended bullet list.

**Backend:** `research/overview/v2/pipeline.py`
**Frontend:** shares `components/overview/bullets/` with v3 (dispatched by response shape in `components/overview/index.tsx`)
**Prompts:** `research/overview/v2/prompts/` (5 section system/user prompts + `synthesis_system.txt` + `synthesis_user.txt`)

**How it works:**
- Stage 1 — run the 5 section agents concurrently (v2 owns its own copies of the agent code and prompts; nothing is imported from v1). Section prompts ask for **plain one-sentence findings with `[N]` citation markers** — no markdown, no headlines, no display formatting. Section outputs are not user-facing; the synthesis step rewrites every bullet from scratch.
- Stage 2 — `synthesis_input.build_dossier()` merges section outputs into one dossier text block plus a single unified citation list, renumbering inline `[N]` markers across sections.
- Stage 3 — one non-tool LLM call with `with_structured_output(_SynthesisBullets)` emits 5–8 blended bullets. The LLM only returns bullets; the unified citation list is assembled in Python from the dossier pool (not round-tripped through the model). The final `ResearchSummary` is constructed from `{bullets: llm_output, citations: dossier_result.unified_citations}`.
- `TOTAL_SECTIONS = 1` — the store only reaches "complete" after synthesis (no per-section streaming to the frontend).

**What v2 is trying to fix:** v1's contradictions and wall-of-text problems. The dossier + single synthesis call gives the LLM global context to prioritize across sections, exercise judgment about what matters, and produce fewer, denser bullets with coherent citations.

**What v2 still carries from v1:** the search cost and token accumulation in the 5 section agents. It's strictly additive — v2 runs everything v1 does, plus a synthesis call.

**Key schema note:** v2 defines its own `ResearchSummary(bullets: list[str], citations: list[Citation])` in `v2/models.py` — it does **not** import from any shared module. `bullets` is required and non-nullable; the initial loading state is an empty list, not `None`. Earlier iterations had `bullets: list[str] | None`, which generated an `anyOf[array, null]` JSON schema that caused Anthropic to occasionally emit `bullets` as a JSON-encoded string (violating the type contract and killing synthesis via a Pydantic validation error). The non-nullable schema removes the ambiguity.

**⚠️ Latency: v2 is the slow variant.** Observed wall-clock from Langfuse traces (2026-04-22 test batch):
- Single senator: 60–180s
- Municipal council member under a full 10-rep batch (with `_semaphore = Semaphore(2)` at module scope): 800+s

Structural reasons, in rough order of impact:
1. **Sequential stages**: every rep pays for Stage 1 (5 section agents) *and then* waits for Stage 3 synthesis. v3 and v1 have no second LLM stage.
2. **Section-agent tail**: slowest section gates everything — one agent hitting `recursion_limit=15` while chasing bad queries burns ~15 sequential LLM+tool turns before the `GraphRecursionError` is caught and synthesis can start. We saw this in the Gillibrand `top_donors` trace.
3. **Global semaphore of 2** in `v2/pipeline.py` serializes concurrent reps past the second one — a 10-rep page fans out into 5 sequential batches. This is v2-only; v1 and v3 don't have it. Worth reconsidering.
4. **Duplicated "who is this person" searches**: each of the 5 section subagents rediscovers baseline facts before starting. A single agent covers that once.

None of these are fixed by the recent synthesis/schema cleanup — the cleanup was correctness, this is throughput. Biggest single latency win would be raising or removing the semaphore; biggest quality-preserving design win would be collapsing to one agent (see "is v2 worth keeping separate from v3?" debate in notes).

---

## V3: Search-Outside-the-Loop + Single Distillation

**Architecture:** The "Recommended direction" from the research section below, implemented. Search happens entirely outside the LLM loop; the LLM only sees pre-fetched snippets at the very end.

**Backend:** `research/overview/v3/pipeline.py` (+ `prefilter.py`)
**Frontend:** shares `components/overview/bullets/` with v2
**Prompts:** `research/overview/v3/prompts/` (`query_gen_system.txt`, `query_gen_user.txt`, `distill_system.txt`, `distill_user.txt`)

**How it works:**
1. **Query generation** — 1 LLM call with `with_structured_output(_QueryList)` emits `OVERVIEW_V3_NUM_QUERIES` (default 15) diverse search queries. No tools.
2. **Parallel search** — Tavily fan-out bounded by `OVERVIEW_V3_SEARCH_CONCURRENCY` (default 5), `OVERVIEW_V3_RESULTS_PER_QUERY` results per query (default 5). No LLM in the loop.
3. **Prefilter** — `prefilter.prefilter_results()` dedupes by URL, truncates snippets to `OVERVIEW_V3_SNIPPET_CHAR_CAP` chars (default 800), caps total at `OVERVIEW_V3_RESULTS_CEILING` (default 60).
4. **Distillation** — 1 LLM call with structured output produces the final `ResearchSummary` (bullets + citations). v3 defines its own `ResearchSummary` in `v3/models.py` with the same shape as v2's — `bullets: list[str]` (required, non-nullable), `citations: list[Citation]`. Because distillation happens once per rep, the old `list[str] | None` schema rarely fired the Anthropic stringify bug in v3, but the fix was applied uniformly.
- `TOTAL_SECTIONS = 1`; everything lands in the store at the end.

**What v3 is trying to fix:** the token accumulation problem described below. Because search results never enter an agent loop, there's no re-reading of snippets on every LLM turn — each snippet crosses the LLM exactly once, in the distillation call.

**Tradeoffs:**
- No adaptive search — if a query surfaces an interesting lead, v3 can't chase it. For a rep overview this is fine (you know what you're looking for upfront); for open-ended research it wouldn't be.
- Query quality matters a lot. Bad queries → nothing good for the distiller to work with.
