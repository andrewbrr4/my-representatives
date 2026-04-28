# V4 Performance & Quality

Ideas for each node in the v4 overview pipeline. Track both **latency** and **quality** improvements (no info we want to surface should be silently dropped).

Pipeline flow: `query_generator → breadth_search → filter → research_agent → formatter`
(The depth subagent is invoked from inside `research_agent` via the `request_depth_research` tool.)

Tag each idea inline:

- **[L]** latency improvement
- **[Q]** quality / coverage improvement (right info surfaced, no important topic dropped)
- **[L+Q]** both

---

## Baseline trace — Chuck Schumer

Run on 2026-04-28, trace `a43f5b07d8c1a40f074cb832ad817e06`. Total 81.4s, $0.31, 33 search calls.

Per-node latency:

| Node              | Latency  | Notes                                                    |
| ----------------- | -------- | -------------------------------------------------------- |
| query_generator   | 6.5s     | 1 LLM call → 18 queries (in=1k, out=306)                 |
| breadth_search    | 7.6s     | 18 parallel Tavily searches → 90 raw results             |
| filter            | 0.002s   | Python dedupe/truncate → 60 results                      |
| research_agent    | **41.3s**| triage LLM (13.5s, in=12k) → 3× depth subagents (≤19.1s) → final LLM (8.6s, in=16.5k) |
| formatter         | **26.0s**| 1 LLM call (in=23.5k, out=1.3k) → 8 bullets / 20 cites   |

Quality observations — topics that returned breadth results but were dropped from the final 8 bullets:

- **Policy positions (immigration / healthcare)** — query #3 issued, no bullet
- **Top donors / campaign finance** — queries #4 + #15 issued, no bullet (this was a first-class section in v1/v2)
- **2026 re-election / NY campaign** — query #6, no bullet
- **Broader foreign-policy stance (Ukraine / Israel)** — query #14, only recent war-powers ultimatum survived
- **Sponsored legislation / 119th Congress voting record** — queries #1, #2, #7, no concrete bullet beyond AI framework

Citation provenance (final 20 citations):

- **11 (55%)** depth-only — depth did pull a lot of *new* URLs
- **8 (40%)** breadth-only
- **1** in both pools, **2** total URL overlaps between breadth and depth (re-fetched)

So depth wasn't ignored — it dominated citations. The problem is **topical**: the 3 depth topics (intra-party criticism / midterm strategy / govt funding) were *already* heavily covered by breadth, so depth reinforced the existing breadth bias rather than filling gaps (donors, voting record, policy positions). Final bullets are over-indexed on the topics the breadth query mix already amplified.

Other quality smells:

- 6 of 8 bullets are DC-political-recency stories from the last 90 days; only 2 touch substance (NY funding, AI)
- A few citations are advocacy/PR sources (DSCC press release, House Appropriations release, YouTube clips, schumer.senate.gov)
- Bullet 4 mixes years ("March 2025") in an otherwise-2026 narrative

---

## query_generator

_Observed: 6.5s for 18 queries, 1 LLM call (in=1k, out=306). Generated queries skewed political-news-y; #16 "Brooklyn career history" was wasted, #4/#15 (donors) returned weak results, several queries overlap (#5/#12 controversies, #4/#15 donors)._

_Ideas:_

- [ ] **[L]** Run on Haiku — output is just a list of query strings, structured-output overhead is the only thing keeping this on Sonnet
- [ ] **[L]** Cache queries per (rep_name, office) for short TTL — same rep on the same day shouldn't regen
- [ ] **[Q]** Force coverage of a fixed taxonomy (policy positions, voting record, donors, recent news, controversies, accomplishments) — generator picks N queries *per* slot rather than N queries total, so policy/donor topics can't get squeezed out
- [ ] **[Q]** Deduplicate / cluster queries before sending to Tavily (the LLM produced near-duplicates like #5 vs #12, #4 vs #15)
- [ ] **[Q]** Pass current date into prompt so generator can request `published_date` filters and avoid generic biographical queries for senior incumbents
- [ ] **[Q]** Different query budgets by office level — a US Senator probably wants more national-policy queries; a city councilor wants more local-news queries

## breadth_search

_Observed: 7.6s for 18 queries × 5 results = 90 raw results, fully parallel. Tail latency is the slowest single Tavily call (~1.5–2s)._

_Ideas:_

- [ ] **[L]** Use Tavily `search_depth=basic` for breadth (faster) and reserve `advanced` for depth — currently both paths use the same setting
- [ ] **[L]** Cap concurrency lower to reduce Tavily rate-limit retries (currently `OVERVIEW_V4_SEARCH_CONCURRENCY=5`); evaluate if 8–10 actually returns faster
- [ ] **[L]** Per-query timeout w/ fallback (drop slowest 1–2 queries if they exceed the p90 latency)
- [ ] **[Q]** Use Tavily's `include_domains` / `exclude_domains` to bias against Facebook/YouTube/press-release domains and toward news + .gov for federal reps
- [ ] **[Q]** Add a date filter (`days=180` or `start_date`) to recency-sensitive queries so we don't waste slots on 2019 NYT articles
- [ ] **[Q]** Per-query `max_results` instead of uniform 5 — broad queries get more, narrow queries get fewer
- [ ] **[L+Q]** Skip duplicate-URL re-fetches across depth and breadth (right now depth issues a near-duplicate query and re-pays Tavily)

## filter

_Observed: 0.002s — pure Python dedupe + truncation. Not a latency hotspot. But this is the only place curation happens before the LLM sees everything._

_Ideas:_

- [ ] **[Q]** Score results before truncation — currently just dedupes URL/title and keeps first N. Add a cheap relevance score (rep name in title/snippet, recency, domain quality) so the 60-result cap doesn't randomly drop the strongest hits
- [ ] **[Q]** Track which query each surviving result came from and enforce per-query minimums (so donor queries don't get crowded out by news queries that returned more results)
- [ ] **[Q]** Drop snippet duplicates, not just URL duplicates (different URLs with near-identical AP-wire snippets)
- [ ] **[Q]** Down-weight social media / video / press-release domains here too, complementary to breadth's `exclude_domains`

## research_agent

_Observed: **41.3s — biggest single contributor.** Triage LLM (13.5s, in=12k tokens) decided to issue 3 `request_depth_research` calls in parallel; depth subagents took up to 19.1s; then a final LLM call (8.6s, in=16.5k tokens) rolled it all up before handing to formatter. The 3 depth topics (intra-party criticism / midterm strategy / govt funding) heavily overlapped each other and the breadth queries._

_Ideas:_

- [ ] **[L]** Stream filtered_results to the formatter directly when `OVERVIEW_V4_DEPTH_ENABLED=false` — already supported but should benchmark "breadth-only" vs full to quantify the depth latency tax
- [ ] **[L]** Move triage to Haiku (it's just picking topics + reasons, not synthesizing)
- [ ] **[L]** Cap parallel depth subagents to 2 (vs. the current `OVERVIEW_V4_AGENT_MAX_DEPTH_CALLS=3`) once we can tell the longest tail dominates anyway
- [ ] **[L]** Skip the final agent reasoning step (8.6s) — let the formatter consume `breadth + depth` directly. The agent's "summary" before formatter doesn't appear to drive bullet selection
- [ ] **[L+Q]** De-duplicate depth topics against breadth queries — if a topic was already heavily covered by breadth, don't dispatch depth on it; force depth to query *gap* angles (this trace showed 55% of citations came from depth, but on topics breadth had already saturated → reinforced bias)
- [ ] **[Q]** Make the triage prompt aware of the coverage taxonomy (donors, policy positions, voting record) — currently it pattern-matches whatever's "fast-moving" in the breadth pool, which is biased toward recent news drama
- [ ] **[Q]** Triage should explicitly enumerate the **under-covered** taxonomy slots (count breadth results per slot, dispatch depth on the slots with `<N` results) rather than picking "interesting" topics
- [ ] **[Q]** Pass the current date + the rep's office level so triage doesn't dispatch depth on stale topics or low-information topics for the office (e.g., a US Senator has a clear voting record we should always probe)

## depth_subagent

_Observed: each subagent did ~3 LLM calls + ~4 depth_tavily_search calls sequentially. Per-subagent latencies 14.1s, 19.1s, 17.0s (parallel, so the longest is the bottleneck). Depth produced 46 new URLs and ended up driving 55% of final citations — so it's earning its keep on volume. The problem is **topic selection**: triage picked 3 topics that breadth already covered heavily, so depth reinforced existing bias instead of filling coverage gaps._

_Ideas:_

- [ ] **[L]** Cap depth recursion lower — `OVERVIEW_V4_DEPTH_RECURSION_LIMIT=8` is generous; 4 might suffice for the topics we actually pick
- [ ] **[L]** Run depth searches in parallel within a single subagent (currently the agent loop serializes them via the LangGraph react pattern)
- [ ] **[L]** Use Haiku for the in-loop reasoning steps (Sonnet for the final summary if needed)
- [ ] **[Q]** Inject the breadth result URLs/titles into the depth subagent's system prompt as "already covered, search for *new* angles" — currently the subagent issues queries that re-find the same articles
- [ ] **[Q]** Force the subagent to read full Tavily content (`include_raw_content=true`) for at least one promising URL per topic, instead of doing 4 snippet searches — better signal for the same wall time
- [ ] **[Q]** Pass `topic` + `reason` from request_depth into the subagent prompt explicitly so the subagent stays anchored on the gap rather than drifting

## formatter

_Observed: **26.0s, in=23.5k tokens, out=1.3k tokens — the second-biggest contributor.** This is where the 90+ search results get distilled to 8 bullets — and where most quality issues land (dropped donors / policy positions / re-election / broader foreign policy)._

_Ideas:_

- [ ] **[L]** Pre-summarize / shrink the input pool before formatter — drop snippets to ~200 chars, drop the lowest-relevance half of results, send only what's needed
- [ ] **[L]** Smaller/faster model for formatter; the shape of work (extract, cite, format) is more pattern-matchy than reasoning-heavy
- [ ] **[L]** Stream the bullets so the user sees the first 1–2 within a few seconds rather than waiting 26s for the full block
- [ ] **[Q]** Force coverage of a section taxonomy (e.g. "you must include at least one bullet on policy positions, one on donors if signal exists, one on recent legislative work, one on controversies") — current free-form prompt lets recency-bias eat slots
- [ ] **[Q]** Allow more bullets when the input is rich — current 5–8 cap is hard, but a US Senator with 60+ results worth covering arguably deserves 10–12
- [ ] **[Q]** Make the formatter explicitly emit "no information found" for a topic when results are weak, instead of silently omitting — surfaces gaps to us in traces and to the user as honesty
- [ ] **[Q]** Down-rank / strip advocacy + PR domains (DSCC, schumer.senate.gov press releases, House Appropriations releases, YouTube) before the formatter sees them, so it can't lean on them as citations
- [ ] **[Q]** Audit the date-mixing bug (bullet 4 says "March 2025" inside an otherwise-2026 narrative) — pass `current_date` into the formatter prompt and instruct it to flag/year-tag dates explicitly
