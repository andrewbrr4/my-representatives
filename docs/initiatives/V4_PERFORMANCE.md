# V4 Performance & Quality

Ideas for each node in the v4 overview pipeline. Track both **latency** and **quality** improvements (no info we want to surface should be silently dropped).

Pipeline flow: `query_generator → breadth_search → filter → research_agent → formatter`
(`research_agent` does a structured-output triage call, then fans out depth subagents in parallel via `asyncio.gather`.)

**Code location:** The v4 pipeline lives at the top level of `backend/research/overview/` (flattened from the previous `research/overview/v4/` location). All path references below (e.g. `nodes/formatter.py`, `tools/tavily_search.py`, prompts in `prompts/`) are relative to that root. Legacy v1/v2/v3 variants live under `research/overview/legacy/`.

---

## All-Haiku experiment (2026-05-12, Hochul) — model-swap mostly paused

**Setup:** Single rep (Kathleen Hochul, NY Governor). Baseline = all Sonnet defaults. Variant = `OVERVIEW_V4_QUERY_GEN_MODEL` / `_TRIAGE_MODEL` / `_DEPTH_MODEL` / `_FORMATTER_MODEL` all set to `claude-haiku-4-5-20251001`.

**Latency / cost (one run each):**

| Node | Sonnet | Haiku-x4 | Delta |
|---|---|---|---|
| query_gen | ~8s | ~5s | -3s |
| breadth_search | ~4s | ~4s | 0 (not LLM-bound) |
| filter | ~0s | ~0s | 0 |
| research_agent | ~18s (triage 8s + 2 depth subagents) | ~1s (triage only — chose `depth_requests=[]`) | **-17s** |
| formatter | ~22s | ~10s | **-12s** |
| **Total** | **51.7s** | **20.0s** | **-61%** |
| **Cost** | $0.148 | $0.030 | **-80%** |

Traces: baseline `52efe655020cbb6e5cf49ca03197e138`, Haiku `2782833615a4cf57ba9600677dd4f019`.

**Quality findings (the real story):**

- **Formatter on Haiku produced clear regressions and a rule violation.** The Haiku formatter emitted "First female New York governor" as bullet 1 — a direct violation of the `formatter_system.txt` "no identity-framing biography" rule. It also dropped substantive-controversy content Sonnet caught (Bills stadium $600M deal, federal corruption probe nearby, 2026 reelection / Delgado primary) in favor of weaker stories. **Importance-pruning is the formatter's load-bearing job, not rendering** — downgrading the model here loses the curation quality that justifies running a research pipeline at all. Sonnet pick the Bills-stadium controversy over a vetoes-count headline; Haiku does the opposite. **Verdict: keep formatter on Sonnet.**
- **Triage on Haiku went too conservative.** Haiku triage chose `depth_requests=[]`. Sonnet's two depth calls (Delgado primary status, federal corruption probe) were both defensible Condition-1 staleness checks against load-bearing facts. **Verdict: keep triage on Sonnet** — depth-firing judgment is the whole point of the node.
- **Depth subagents** — not directly evaluable in this run (Haiku triage skipped depth). Until we have evidence, **keep on Sonnet** by default; the verification job is multi-step reasoning over noisy source material.
- **Query gen on Haiku looked fine but the win is too small to justify follow-up.** Generated a reasonable 18-query list against the bucket taxonomy. Downstream nodes don't care which model wrote the query strings. But the math is unconvincing: query_gen ran on 1,659 input + 382 output tokens. Sonnet $0.0105/rep vs Haiku $0.0035/rep = **~$0.007/rep saved (~5% of total run cost)**, and **~3s latency saved out of 51.7s (~6%)**. At any plausible volume this is not user-perceptible and not financially meaningful. Switching also requires the mixed-model cost-tracking fix below as a prerequisite (week-ish of infra work). **Verdict: shelved.**

**Status of the four Haiku env vars after this experiment: all four paused.** Env vars stay in place as escape hatches and to enable future experiments, but **production defaults to Sonnet for every node**. The latency lever is no longer model-swap — pivot to the non-model wins below.

> Model-swap is no longer the most-leveraged latency lever. Pivot to:
> 1. **Streaming the formatter output** (open `[L]` item) — perceived-latency win without quality cost. User sees first bullets in ~5–8s instead of waiting 22s for the full block.
> 2. **Pre-shrinking the formatter's input pool via Python-side ranking in `filter`** (open `[L]` item) — formatter is 22s on 23k input tokens; halve the input and you halve the time without changing the model.
> 3. **Per-query timeout w/ fallback in breadth_search** (open `[L]` item) — drop the slowest 1–2 Tavily calls past p90.

## Known limitation: cost tracking can't handle mixed models

**Surfaced 2026-05-12** while planning the query_gen Haiku swap. **Not currently blocking anything** — all four Haiku swaps are shelved (see "All-Haiku experiment" section), so prod runs every node on Sonnet and the single-price env-var math is correct. Documenting here for whenever a future model-mix experiment justifies the infra work.

- `research/usage.py` aggregates `input_tokens` + `output_tokens` across every LLM call in a run into one `UsageStats` (no per-model breakdown).
- `db.py:save_research_task` / `save_transactions` apply a single `input_cost_per_m` / `output_cost_per_m` pair (from `ANTHROPIC_INPUT_COST_PER_M` / `ANTHROPIC_OUTPUT_COST_PER_M` env vars) to that aggregate.
- Sonnet pricing is ~3× Haiku pricing on both input ($3/M vs $1/M) and output ($15/M vs $5/M). A run that mixes models will be off by up to 3× depending on which model dominates token volume and which price the env var was set to.

**Fix shape (sketch, not committed):**

1. `UsageTracker` keeps `dict[model_name, UsageStats]` instead of a single aggregate. Each `on_llm_end` callback already carries the model name via `response_metadata.model_name`.
2. Add a price table — either as env vars (`ANTHROPIC_PRICE_SONNET_INPUT_PER_M`, `ANTHROPIC_PRICE_HAIKU_INPUT_PER_M`, etc.) or as a small Python constant module that future model swaps update.
3. `save_transactions` accepts `usage_by_model` and writes one outflow `transactions` row per model used (preserves per-model audit trail in the ledger).
4. `research_tasks` schema currently stores `model` as a single string and `input_cost_per_m` / `output_cost_per_m` as single columns. Options: (a) keep aggregate columns but compute as a token-weighted average (lossy for analytics), (b) add a `model_breakdown jsonb` column with `{model: {input, output, cost}}`, (c) move the breakdown entirely to `transactions` (already per-model) and treat `research_tasks` aggregate as the rollup.

Option (c) is the smallest blast radius: `transactions` already exists for ledger-per-cost-source, so writing N rows per task (one per model + one for search) and computing aggregates in queries is natural. Option (b) is more queryable but adds a schema column. **Recommendation (whenever this is revisited): c, with the `research_tasks.model` column repurposed to a comma-separated list or "mixed".**

**Trigger to revisit this:** any future experiment where a node-specific model swap shows a quality-neutral win large enough to justify ~a week of infra work. Today's Haiku numbers don't clear that bar.

Tag each idea inline:

- **[L]** latency improvement
- **[Q]** quality / coverage improvement (right info surfaced, no important topic dropped)
- **[L+Q]** both

---

## Pipeline philosophy

**Taxonomy (5 buckets, revised 2026-04-29):**

1. **Role / leadership / committees** — always-include if signal exists
2. **Signature priorities & legislative record** — 1-2 issues this rep is *known for* + key votes; query_gen forced to cover sub-axes (domestic + foreign, economic + social) so the breadth pool gives a 360° view of policy positioning
3. **Donors / campaign finance** — top industry + up to ~3 PACs; individual donors only if Musk-tier prominence (no need to name many specific donors — this isn't OpenSecrets)
4. **Public statements & press coverage** — what they're saying, how the press is treating them
5. **Substantive controversies** — ethics complaints / investigations / lawsuits / FEC / formal sanctions / conduct-in-office qualify; viral social media moments, AI-deepfake drama, single-news-cycle gaffes, and book launches do NOT

Dropped from the earlier 7-bucket version (2026-04-28): **district / constituency context** (too magnetic for things done *to* the rep's state by others — we want rep agency) and **recent news** (duplicative of public statements & press coverage). Shipped prompts (`query_gen_system.txt`, `formatter_system.txt`) still reference the 7-bucket list and need to be re-shipped against 5 — see per-node ideas below.

**Pipeline flow:**

> **Breadth casts a wide net per bucket** — query_gen issues queries covering each bucket's sub-axes. **Sub-axes are LLM-decided per office level**, not hardcoded: a US Senator's "Signature priorities" sub-axes span domestic/foreign/economic/social policy; a mayor's span housing/public safety/transit/schools/local budget. The query_gen prompt directs the LLM to identify relevant sub-areas for *this* rep's office before generating queries, and to skip sub-areas the office doesn't have (no foreign policy for a city councilor). Total query budget capped at ~25-30; the LLM prioritizes across buckets/sub-axes within that ceiling. Output schema stays flat (`_QueryList`) for now — structured `{bucket, subarea, query}` output is a future upgrade if traces show coverage gaps that need per-sub-area auditing. The goal at this stage is broad initial coverage, not precision.
>
> **Optional depth subagents sweep up the stragglers** — they fill in gaps where a bucket came back thin from breadth, or verify load-bearing claims that look stale. Depth is a backstop, not a deep-dive engine; default is "no depth needed." Depth is expensive — only fire when really needed.
>
> **Formatter does two jobs:**
> 1. **Group / condense** related findings within a bucket into a single bullet (e.g. all economic-policy findings → one economic bullet; "Schumer surrender" + low-approval news cycle → one "leadership effectiveness" bullet).
> 2. **Prune by importance** — items with thin coverage or low salience drop out.

By the time the formatter runs, the pool should give a 360° view per bucket. **Importance-pruning is currently LLM judgment** (option A from the 2026-04-29 design discussion): the formatter is told to "weight items by how broadly and prominently covered — a shutdown vote across 8 outlets outweighs a single op-ed; authoritative single sources (Congress.gov, OpenSecrets, Senate Ethics filings) can outweigh many low-quality mentions." Aiming for ~8-12 bullets total. If traces show weak items winning slots over well-covered ones, upgrade to a hybrid where `filter_node` attaches a Python-counted unique-outlet signal as a tiebreaker.

This section is the canonical statement; the per-node ideas below should be read with this framing in mind.

---

## Direction (aligned)

A few framing decisions from reviewing the trace:

- **Depth's real job is stale-info correction, not "deep-dive on hot topics."** The original motivation for depth was egregious staleness — a rep listed as running for office whose campaign already ended; a court case shown as ongoing that's actually settled. Triage on this trace fired 3× to dive into ongoing political drama (intra-party criticism, govt funding) — none of that needed depth, breadth already had it. Depth should fire **rarely** and only when a breadth result looks potentially-stale-and-load-bearing (campaign status, pending legal matters, leadership/role changes). Default mode for most reps should be breadth-only.
- **Introduce a bucket taxonomy** to fix the "important topics silently dropped" failure mode. The current 7 buckets, after revision (2026-04-28 review): **role/leadership/committees**, **signature priorities & legislative record**, **donors / campaign finance**, **public statements & press coverage**, **substantive controversies**, **recent news**, **district / constituency context**. *(Revised again 2026-04-29 to 5 buckets — dropped "district / constituency context" and "recent news"; see **Pipeline philosophy** section above for the canonical taxonomy. Shipped prompts still reference the 7-bucket list and need to be re-shipped.)* Two notable revisions from earlier rev:
  - Dropped "Policy positions" as a stand-alone bucket — a separate `issue-research` pipeline handles per-issue stance lookups, and surveying every issue stance was crowding out signal. Replaced with **"Signature priorities & legislative record"** (1–2 issues this rep is *known for*, e.g. Schumer→AI policy, Sanders→Medicare for All, Warren→consumer protection). The voter-overview job is "what are they about" not "what do they think about every issue."
  - "Controversies" → **"Substantive controversies"** with explicit exclusions: ethics complaints / investigations / lawsuits / FEC / formal sanctions / conduct-in-office qualify; viral social media moments, AI-generated content drama (deepfakes, AI videos), and single-news-cycle gaffes do NOT. Real-rep traces showed tabloid-y items leaking into the controversy slot — the framing now actively excludes them.
  - **No identity-framing biography** — added as a separate strict rule in `formatter_system.txt`: skip "first [demographic] in [office]" headlines. Same de-noise theme as substantive-controversies — biographical color isn't substantive coverage. If identity directly shaped specific work, the work itself becomes the bullet, not the identity label.
  - **"Role, leadership & committees"** is now a "always include if signal exists" bucket — basic "who is this person in their institution" should never be omitted (committees, leadership positions, ranking-member status).

  *How* to enforce the taxonomy is the open implementation question — options ordered cheapest-first:
  1. **Taxonomy via prompts only** (simplest): inject the bucket list into `query_generator` (queries-per-bucket) and `formatter` (must-attempt-coverage). One round of prompt edits, zero architectural change. Try this first — it may be enough.
  2. **Add explicit categorization** (medium): after `filter`, attach a `bucket` field to each result via Python rules + small LLM batch call. `formatter` consumes pre-categorized input. Buys auditability of what landed where.
  3. **Full decompose: categorize → score → render** (heaviest, per a recent design suggestion): three explicit phases — Python/Haiku categorize, deterministic per-bucket scoring, formatter renders only top-k buckets with explicit "no information found" for weak ones. Highest auditability + tunability, but most moving parts; only worth it if (1) and (2) prove insufficient.

  Whatever level we pick, the taxonomy becomes **shared infrastructure** if we want it to: `query_generator` per-bucket queries, `filter` categorization, `research_agent` triage on weak buckets, `formatter` top-k rendering. Cheaper levels (option 1) only touch a couple of nodes.

  **Open question — is the taxonomy user-visible?** Three options here too:
  - **Hidden** (LLM-only process tool, flat bullets out): keeps v4's compact style; preserves narrative flow; but coverage gaps stay invisible to the user, which is the exact failure mode we're trying to fix.
  - **Visible inline labels**: each bullet rendered with its bucket tag (e.g. `**Donors** — Schumer raised $X from...`); compact "no info found" entries for high-priority buckets that scored 0 (donors, voting record, policy positions). Builds trust without v1-style structural padding.
  - **Visible v1-style sections**: explicit section headers with skeletons during loading. Highest trust signal, matches civic-info-product norms (BallotPedia-ish), but heaviest UI footprint.

  Prerequisite for surfacing gaps: scoring/categorization must be observable in traces *before* we tell users "no info found" — a category that returned 0 because of a bad bucket assignment would be worse than silent omission.
- **Aggressive domain filtering at the breadth/filter layer** (drop press releases, advocacy domains, YouTube, social) — these are 100% biased and currently leak through to citations.
- **Pre-formatter shrinking has a latency tradeoff** — adding a separate LLM "filter/curate" call to shrink the formatter's input may not net-reduce wall time (you pay for two sequential LLM calls instead of one big one, unless the curation can run on Haiku and the formatter shrinks proportionally). Worth measuring before committing. Cheaper alternatives first: smaller snippets, smarter Python-side ranking in `filter`, domain blocklists.

---

## query_generator

_Observed: 6.5s for 18 queries, 1 LLM call (in=1k, out=306). Generated queries skewed political-news-y; #16 "Brooklyn career history" was wasted, #4/#15 (donors) returned weak results, several queries overlap (#5/#12 controversies, #4/#15 donors)._

_Ideas:_

- [x] **[L]** Run on Haiku — output is just a list of query strings, structured-output overhead is the only thing keeping this on Sonnet — _evaluated and shelved 2026-05-12: Haiku output quality on the Hochul A/B (trace `2782833615a4cf57ba9600677dd4f019`) looked fine. But the win is ~$0.007/rep and ~3s/rep — not financially meaningful, not user-perceptible — and capturing it would require the mixed-model cost-tracking infra work as a prerequisite. ROI doesn't justify it. **Default sticks with Sonnet** across all four nodes. See "All-Haiku experiment" section above._
- [x] **[Q]** Force coverage of a fixed taxonomy (policy positions, voting record, donors, recent news, controversies, accomplishments) — generator picks N queries *per* slot rather than N queries total, so policy/donor topics can't get squeezed out — _shipped (prompt-only, level-1 of taxonomy approach): `query_gen_system.txt` requires ≥2 queries per bucket across 7 buckets. **Taxonomy revised 2026-04-28** based on real-rep trace feedback: dropped "Policy positions" (issue-research pipeline handles that), added **Role/leadership/committees**, reframed accomplishments as **Signature priorities & legislative record** (1–2 known-for issues), tightened controversies to **Substantive controversies** (excludes viral / AI-deepfake / tabloid). See Direction section for full taxonomy + rationale._
- [x] **[Q]** Deduplicate / cluster queries before sending to Tavily (the LLM produced near-duplicates like #5 vs #12, #4 vs #15) — _shipped (exact-match only): `query_generator.py` now dedupes by case/whitespace-normalized form before fan-out. Catches obvious duplicates; near-duplicate clustering (token-overlap similarity) remains a follow-up if real traces still show topical near-duplicates after the new prompt's diversity rules._
- [x] **[Q]** Pass current date into prompt so generator can request `published_date` filters and avoid generic biographical queries for senior incumbents — _partially shipped: `current_date` was already substituted into `query_gen_system.txt`, and the rewritten prompt drops the biographical bucket entirely (which was the wasted slot in the Schumer trace, #16 "Brooklyn career history"). Per-query Tavily date filters remain a follow-up (needs per-query metadata, see breadth_search idea on date filter)._
- [ ] **[Q]** Different query budgets by office level — a US Senator probably wants more national-policy queries; a city councilor wants more local-news queries
- [x] **[Q]** **Office-adaptive sub-axes within each bucket** — query_gen prompt instructs the LLM to identify the sub-areas relevant to *this* rep's office level before generating queries, with ≥1 query per sub-area where signal is plausible. Replaces the prior "≥2 queries per bucket" hardcoded rule with adaptive coverage matching the breadth of the office (Senator: domestic/foreign/economic/social + hot topics; mayor: housing/transit/schools/local budget; etc.). Flat `_QueryList` output preserved; structured `{bucket, subarea, query}` output is a future upgrade if traces show coverage gaps that need per-sub-area auditing. — _shipped 2026-04-29: `query_gen_system.txt` rewritten against 5-bucket taxonomy with sub-area instructions. **Follow-up:** bump `OVERVIEW_V4_NUM_QUERIES` default from 18 → 25-30 to match the philosophy doc's target query budget; current default still produces 18 queries which constrains how broadly sub-areas can be covered._

## breadth_search

_Observed: 7.6s for 18 queries × 5 results = 90 raw results, fully parallel. Tail latency is the slowest single Tavily call (~1.5–2s)._

_Ideas:_

- [x] **[L]** Use Tavily `search_depth=basic` for breadth (faster) and reserve `advanced` for depth — currently both paths use the same setting — _confirmed already: Tavily SDK default for `search_depth` is `basic`, and `tavily_search_raw` doesn't pass an override. Both breadth and depth currently run on `basic`. If we want depth to use `advanced`, that's a follow-up — the default is correct for breadth's needs._
- [ ] **[L]** Cap concurrency lower to reduce Tavily rate-limit retries (currently `OVERVIEW_V4_SEARCH_CONCURRENCY=5`); evaluate if 8–10 actually returns faster
- [x] **[L]** **Lift the global Tavily semaphore from hardcoded 3 to env-driven (default 20).** `research/search.py` had `_search_semaphore = asyncio.Semaphore(3)` — a process-global cap that ALL pipelines (v1/v2/v3/v4 breadth + depth, elections, issues) funneled through. Per-pipeline caps like `OVERVIEW_V4_SEARCH_CONCURRENCY=5` were silently overridden. With 5 reps fanning out 18 queries each (90 total), 3 slots meant ~30 sequential batches per rep. — _shipped 2026-05-01: now `TAVILY_GLOBAL_CONCURRENCY` (default 20). Verified ~30% reduction in total v4 wall time on a 5-rep parallel run; breadth-search stage dropped from ~27s to ~5–8s per rep. Tavily paid tier supports 100 RPS so 20 is well within limits._
- [ ] **[L]** Per-query timeout w/ fallback (drop slowest 1–2 queries if they exceed the p90 latency)
- [x] **[Q]** Use Tavily's `include_domains` / `exclude_domains` to bias against Facebook/YouTube/press-release domains and toward news domains — _shipped: `_DEFAULT_EXCLUDE_DOMAINS` in `research/search.py`, env-overridable via `TAVILY_EXCLUDE_DOMAINS`. Excludes social/video + party committees (DSCC/DCCC/etc.). Tavily filter is domain-only — politician self-press subpaths (e.g. `schumer.senate.gov/newsroom/press-releases/...`) need a separate URL-path filter, see follow-up below._
- [x] **[Q]** URL-path filter for politician self-press releases — Tavily can't filter by path, so add Python-side regex in `filter` node to drop `*.senate.gov/newsroom/press-release*`, `*.house.gov/news/...`, and `appropriations.house.gov/news/press-releases/*` patterns. Without this, blanket-excluding `senate.gov`/`house.gov` from Tavily would also kill legitimate `congress.gov` cross-references, voting record pages, etc. — _shipped: `_is_self_press()` in `filter_node.py` drops URLs matching `*.{senate,house}.gov` + path containing `/newsroom/`, `/news/press`, `/press-release`, `/press_release`. Verified with the 3 self-press URLs from the Schumer trace + 4 legit URLs that pass through. Drop count is logged._
- [ ] **[Q]** Add a date filter (`days=180` or `start_date`) to recency-sensitive queries so we don't waste slots on 2019 NYT articles
- [ ] **[Q]** Per-query `max_results` instead of uniform 5 — broad queries get more, narrow queries get fewer
- [ ] **[L+Q]** Skip duplicate-URL re-fetches across depth and breadth (right now depth issues a near-duplicate query and re-pays Tavily)

## filter

_Observed: 0.002s — pure Python dedupe + truncation. Not a latency hotspot. But this is the only place curation happens before the LLM sees everything._

_Ideas:_

- [ ] **[Q]** Score results before truncation — currently just dedupes URL/title and keeps first N. Add a cheap relevance score (rep name in title/snippet, recency, domain quality) so the 60-result cap doesn't randomly drop the strongest hits
- [ ] **[Q]** Track which query each surviving result came from and enforce per-query minimums (so donor queries don't get crowded out by news queries that returned more results)
- [x] **[Q]** Drop snippet duplicates, not just URL duplicates (different URLs with near-identical AP-wire snippets) — _shipped: `_snippet_dedupe_key()` in `filter_node.py` normalizes the first 200 chars (lowercased, whitespace-collapsed) and dedupes against an in-pass set. Drop count is logged._
- [x] **[Q]** Down-weight social media / video / press-release domains here too, complementary to breadth's `exclude_domains` — _shipped: covered by the combination of `_DEFAULT_EXCLUDE_DOMAINS` in `search.py` (Tavily-side: social/video/party committees) + `_is_self_press()` in `filter_node.py` (Python-side: politician/committee press-release URL paths). Both layers logged separately. If specific advocacy domains slip through in real traces, add to `TAVILY_EXCLUDE_DOMAINS`._

## research_agent

_Observed: **41.3s — biggest single contributor.** Triage LLM (13.5s, in=12k tokens) decided to issue 3 `request_depth_research` calls in parallel; depth subagents took up to 19.1s; then a final LLM call (8.6s, in=16.5k tokens) rolled it all up before handing to formatter. The 3 depth topics (intra-party criticism / midterm strategy / govt funding) heavily overlapped each other and the breadth queries — and arguably **none of them needed depth** for this rep. Depth's real purpose is stale-fact correction (campaign ended? case settled? out of office?), not "dig deeper into the hot story."_

_Ideas:_

- [x] **[L+Q]** **Reframe triage around staleness, not interestingness.** Triage prompt should look for breadth results that assert a load-bearing time-sensitive fact (running for office / pending case / current role) and only fire depth to verify those. Default decision should be "no depth needed." — _shipped: `research_agent_system.txt` rewritten with "Default decision: do NOT call depth research." Triggering now requires identifying a *specific factual claim* that is (1) time-sensitive, (2) materially misleading if outdated, AND (3) older than 60 days or undated. Concrete qualifying examples (candidacy status, pending litigation, leadership role) and concrete non-qualifying examples (active news coverage, voting record, donors) included._
- [x] **[Q]** **Add Condition 2: thin-coverage trigger for depth.** Triage now accepts a second justification for depth — when a high-priority bucket is *egregiously* thin in breadth (zero supporting snippets with actual content, OR only generic landing/methodology pages with no real signal), AND that bucket is plausibly retrievable for this rep's office level. High bar: depth is expensive, so this fires only when a bucket is truly missing for a rep where it should exist (e.g. a US Senator with zero usable donor data; a longtime committee chair with no role/leadership signal). Does NOT fire just because a bucket is "lighter than the others." — _shipped 2026-04-29: `research_agent_system.txt` updated with two-condition framing (Condition 1 = stale load-bearing fact; Condition 2 = egregiously thin coverage)._
- [x] **[L]** Add an explicit "skip depth" path in triage so a fast structured-output decision can avoid spawning subagents at all — most runs probably don't need depth — _addressed via the prompt rewrite above. The new prompt makes "zero depth calls" the explicit default outcome. (No code change yet — the structured-output skip path remains a follow-up if prompt-level steering proves insufficient.)_
- [x] **[L]** Stream filtered_results to the formatter directly when `OVERVIEW_V4_DEPTH_ENABLED=false` — already supported; benchmark breadth-only vs full to quantify the depth latency tax we're paying for marginal value — _confirmed already shipped: `research_agent.py` short-circuits to empty `depth_search_results` when `OVERVIEW_V4_DEPTH_ENABLED=false`. Benchmarking is the open action — flip the env var in dev and run a few reps. Now that the triage prompt has been reframed to default-no-depth, the gap between the two modes should be smaller anyway._
- [x] **[L]** Move triage to Haiku (it's just picking topics + reasons, not synthesizing) — _evaluated and paused 2026-05-12: Haiku triage on the Hochul A/B chose `depth_requests=[]`, skipping two depth calls Sonnet had judged worthwhile (Delgado primary status, federal corruption probe — both defensible Condition-1 staleness checks). Triage IS judgment, not template-filling; smaller model is too conservative. Env var stays available but **default sticks with Sonnet**. See "All-Haiku experiment" section above._
- [ ] **[L]** Cap parallel depth subagents to 1–2 (vs. current `OVERVIEW_V4_AGENT_MAX_DEPTH_CALLS=3`) — the staleness use-case rarely needs more than one verification at a time
- [x] **[L]** Skip the final agent reasoning step — let the formatter consume `breadth + depth` directly. The agent's "summary" before formatter doesn't drive bullet selection. — _shipped 2026-04-30: `research_agent.py` is no longer a `create_react_agent`. Now it's a structured-output triage call (`_TriageOutput.depth_requests`) followed by `asyncio.gather` over depth subagents. Removes (a) the react loop's "think between tools" steps and (b) the serial dispatch of depth subagents. `_MAX_DEPTH_CALLS` is now hard-enforced in code instead of being a soft prompt signal. `request_depth_research` tool and `ResearchAgentState` schema deleted as dead code. Latency win on the Schumer trace: ~13s reclaimed (depth-2 was previously waiting on depth-1 to finish in the react loop)._
- [x] **[Q]** Pass the current date + rep office level into triage so it can spot staleness signals (e.g. "running for X" vs current date) — _shipped: `current_date` was already substituted into `research_agent_system.txt`. Office level is in the user prompt via `$office`. The new prompt explicitly references `${current_date}` for the "older than 60 days" check._

## depth_subagent

_Observed: each subagent did ~3 LLM calls + ~4 depth_tavily_search calls sequentially. Per-subagent latencies 14.1s, 19.1s, 17.0s (parallel, so the longest is the bottleneck). Depth produced 46 new URLs and ended up driving 55% of final citations — but on topics breadth had already saturated, so it reinforced existing bias rather than filling gaps. Per the "Direction" section above, depth should fire **rarely** to verify potentially-stale facts, not deep-dive on hot topics._

_Ideas:_

- [ ] **[L]** Cap depth recursion lower — `OVERVIEW_V4_DEPTH_RECURSION_LIMIT=8` is generous; 3–4 should suffice for a "verify one fact" use-case
- [x] **[L]** Run depth searches in parallel within a single subagent (currently the agent loop serializes them via the LangGraph react pattern) — _shipped (prompt-only): `depth_agent_system.txt` now explicitly instructs "Issue your queries in parallel in a single tool-use turn — emit 2 or 3 ``depth_tavily_search`` calls together rather than one-at-a-time. This cuts the subagent's wall time roughly in half." Modern Anthropic models do parallel tool-use when prompted; if real traces show serial behavior persisting, fallback is to make depth not a react agent and instead run a fixed-shape parallel fan-out._
- [x] **[L]** Use Haiku for the in-loop reasoning steps — _evaluated and paused 2026-05-12: not directly testable in the Hochul A/B because Haiku triage skipped depth entirely. Until we have evidence that Haiku can do multi-step fact-verification reasoning over noisy source material without quality regression, **default sticks with Sonnet**. Env var remains available for future A/B once we have a way to force-fire depth on a Haiku run. See "All-Haiku experiment" section above._
- [x] **[Q]** Reshape the subagent prompt around fact-verification: "given this breadth-result claim, find sources confirming or contradicting it as of {current_date}" — instead of the open-ended "research this topic" — _shipped: `depth_agent_system.txt` rewritten as "focused fact-verification agent" with "stay narrow" rules. 2–3 well-targeted queries on the specific factual status, stop early if uncontroversial._
- [ ] **[Q]** Force the subagent to read full Tavily content (`include_raw_content=true`) for at least one promising URL — verification needs the article body, not snippets
- [x] **[Q]** Pass `topic` + `reason` from request_depth into the subagent prompt explicitly so the subagent stays anchored on the verification target rather than drifting — _already shipped before this initiative: `depth_agent_user.txt` already substitutes `$topic` and `$reason`. Marking confirmed._
- [x] **[L+Q]** **Truncate depth Tavily snippets at `OVERVIEW_V4_SNIPPET_CHAR_CAP`** — depth tool was returning full Tavily `content` (often 2k–5k chars) into both `search_results` and the agent-loop `ToolMessage`, so depth-step-2 input was 58k tokens (one parallel-search turn carried ~15 untrimmed Tavily blocks). Now applies the same 800-char cap that breadth's `filter_node` uses. Symmetric with breadth. **Known follow-up — split the cap:** the agent-loop `ToolMessage` only needs ~200 chars per result to plan its next move, while the formatter benefits from the full content. Single-cap conflates the two and is over-tight for the formatter / over-loose for the planner. — _shipped 2026-04-30 in `tools/tavily_search.py`._

## formatter

_Observed: **26.0s, in=23.5k tokens, out=1.3k tokens — the second-biggest contributor.** This is where the 90+ search results get distilled to 8 bullets — and where most quality issues land (dropped donors / policy positions / re-election / broader foreign policy)._

_Ideas:_

- [ ] **[L]** Pre-shrink the input pool **without an extra LLM call** — drop snippets to ~200 chars, drop the lowest-relevance half via Python-side ranking in `filter`, blocklist domains. Two sequential LLM calls (curate → format) probably won't beat one big formatter call unless the curate step is on Haiku and the formatter shrinks proportionally — measure before committing
- [x] **[L]** Smaller/faster model for formatter; the shape of work (extract, cite, format) is more pattern-matchy than reasoning-heavy — _evaluated and paused 2026-05-12: **prior framing was wrong.** The formatter's load-bearing job isn't extract/cite/format, it's the importance-pruning step — grouping ~90 results into 8 bullets that surface the *right* stories. Haiku formatter on the Hochul A/B (a) violated the `formatter_system.txt` "no identity-framing biography" rule by leading with "First female New York governor" and (b) dropped the Bills stadium $600M controversy, the federal corruption probe, and the 2026 Delgado primary in favor of weaker headlines. The curation IS the quality. Latency was 22s → 10s but the bullets weren't equivalent. Env var remains available but **default sticks with Sonnet**. See "All-Haiku experiment" section above._
- [ ] **[L]** Stream the bullets so the user sees the first 1–2 within a few seconds rather than waiting 26s for the full block
- [x] **[Q]** Force coverage of a section taxonomy (e.g. "you must include at least one bullet on policy positions, one on donors if signal exists, one on recent legislative work, one on controversies") — current free-form prompt lets recency-bias eat slots — _shipped (prompt-only): `formatter_system.txt` lists the 7 buckets, asks for 1-3 bullets per bucket where signal exists, skip-entirely if quality bar not met. Mirrors `query_gen_system.txt`. **Revised 2026-04-28**: "Role, leadership & committees" is now an "always include if signal exists" bucket; "Substantive controversies" has explicit exclusions for viral/AI-deepfake/tabloid content; "Signature priorities" replaces broad policy-position survey._
- [x] **[Q]** **Reframe formatter as group/condense + prune by importance** — formatter prompt now opens with "your two jobs": (1) group related findings within a bucket into a single bullet (all economic-policy findings → one economic bullet; controversy + polling reaction → one bullet), (2) prune by importance via LLM judgment weighting on coverage breadth (option A from the design discussion — broad outlet coverage outweighs single mentions; authoritative single sources like Congress.gov / OpenSecrets / Senate Ethics filings can outweigh many low-quality mentions). Also: 7→5 bucket taxonomy revision (dropped "recent news" and "district / constituency context"); added explicit **rep-agency requirement** (don't surface things done *to* the rep's state by other actors); added "book launches" to the substantive-controversies exclusion list; donors guidance refined to "shape, not names" (top industry + up to ~3 PACs, individuals only if Musk-tier); bullet count target raised to 8–12. — _shipped 2026-04-29: `formatter_system.txt` rewritten._
- [x] **[Q]** Allow more bullets when the input is rich — current 5–8 cap is hard, but a US Senator with 60+ results worth covering arguably deserves 10–12 — _shipped: cap raised from 5–8 to 6–12 in `formatter_system.txt`._ **Reversed 2026-05-01:** raising the cap was a regression. Real-rep traces (Trump 12 / 36 citations, Gillibrand 10 / 21) overflowed the "hyper-consumable" intent. Tightened to 5–7 / ~10–18 words; user judgement was that *too* concise. **Final landing: 6–8 bullets, ~14–22 words per bullet** (between the verbose 8–12 and the over-tight 5–7). Both `formatter_system.txt` and `formatter_user.txt` aligned at 6–8 with per-bucket cap of 1–2.
- [ ] **[Q]** Make the formatter explicitly emit "no information found" for a topic when results are weak, instead of silently omitting — surfaces gaps to us in traces and to the user as honesty
- [x] **[Q]** **Schema reliability — flatten + retry + recency-positioned reminder.** Original v4 formatter schema was `bullets: list[_Bullet(text, source_urls)]`; Sonnet 4.6 stringified that nested array (returned `bullets` as `'[\n  {\n  "text"...'`) on ~40% of runs, breaking Pydantic validation and producing silent failures (null `summary`). Three rounds of fixes: (a) flatten schema to two parallel top-level lists `bullet_texts: list[str]` + `bullet_sources: list[list[str]]` — same shape v2/v3 use reliably; (b) wrap the call in LangChain's `with_retry(retry_if_exception_type=(ValidationError,), stop_after_attempt=2)` — empirically the second attempt emits the correct shape; (c) end the user prompt with an explicit primacy/recency reminder showing the JSON-array shape vs. the stringified form (the schema instruction now sits at the *last* thing the model reads, after ~25k tokens of breadth+depth blocks). One earlier attempt at a custom `_invoke_with_repair` with `include_raw=True` was rolled back in favor of the standard LangChain retry primitive (simpler surface, same protection). — _shipped 2026-05-01 in `nodes/formatter.py` + `formatter_user.txt`. Failure rate observed at 0% across 5 reps post-fix._
- [x] **[Q]** **Drop hallucinated citation URLs.** `_build_citations` in `formatter.py` previously added any URL the LLM cited to the user-facing citations list, falling back to URL-as-title for URLs not in the breadth+depth pool. Real traces showed the LLM occasionally citing plausible-looking URLs from training data (e.g. real-looking Reuters URLs that aren't in the actual search results). Now those URLs are silently dropped and the bullet reaches the user with one fewer `[N]` marker (or none). Drop count is logged so we can monitor hallucination rate. — _shipped 2026-05-01. Follow-up if hallucination rate is non-trivial: if a bullet's *only* cited URL was hallucinated, consider dropping the bullet entirely rather than showing it uncited._
- [x] **[Q]** **Stop swallowing formatter ValidationError.** When both retry attempts of `with_structured_output` fail, the formatter previously caught the `ValidationError` and returned an empty `_FormatterOutput()`. The pipeline then completed "normally" with `bullets=[]`, so the store marked the task `status=complete` instead of `failed`. Frontend's `ResearchContent` saw `bullets.length === 0` and rendered the loading skeleton — visually identical to "still loading" forever (smoke test on Antonio Reynoso surfaced this 2026-05-01). Two-layer fix: (1) `formatter.py` now lets the `ValidationError` propagate; the pipeline's existing exception handler returns `(None, total)`, the router calls `store.fail(research_id)`, and the frontend's `failed` UI branch fires — showing "Research unavailable" + Retry. (2) Defensive frontend guard: `RepCard` now also treats `complete + bullets.length===0` as a failure (using `isBullets(summary) && summary.bullets.length === 0`) — protects against any future code path that could repeat this silent-failure pattern. — _shipped 2026-05-01._
- [x] **[Q]** Down-rank / strip advocacy + PR domains (DSCC, schumer.senate.gov press releases, House Appropriations releases, YouTube) before the formatter sees them, so it can't lean on them as citations — _shipped: same combination as above (Tavily exclude_domains for DSCC/YouTube; filter_node self-press URL filter for politician PR pages). Formatter never sees these now._
- [x] **[Q]** Audit the date-mixing bug (bullet 4 says "March 2025" inside an otherwise-2026 narrative) — pass `current_date` into the formatter prompt and instruct it to flag/year-tag dates explicitly — _shipped: `current_date` was already passed into `formatter_system.txt` (just not used as a disambiguation rule). Added a strict rule requiring the year to be explicit on every date in a bullet ("in March 2025" not "in March")._
