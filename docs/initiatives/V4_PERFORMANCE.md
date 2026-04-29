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

## Direction (aligned)

A few framing decisions from reviewing the trace:

- **Depth's real job is stale-info correction, not "deep-dive on hot topics."** The original motivation for depth was egregious staleness — a rep listed as running for office whose campaign already ended; a court case shown as ongoing that's actually settled. Triage on this trace fired 3× to dive into ongoing political drama (intra-party criticism, govt funding) — none of that needed depth, breadth already had it. Depth should fire **rarely** and only when a breadth result looks potentially-stale-and-load-bearing (campaign status, pending legal matters, leadership/role changes). Default mode for most reps should be breadth-only.
- **Introduce a bucket taxonomy** to fix the "important topics silently dropped" failure mode. The current 7 buckets, after revision (2026-04-28 review): **role/leadership/committees**, **signature priorities & legislative record**, **donors / campaign finance**, **public statements & press coverage**, **substantive controversies**, **recent news**, **district / constituency context**. Two notable revisions from earlier rev:
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

- [x] **[L]** Run on Haiku — output is just a list of query strings, structured-output overhead is the only thing keeping this on Sonnet — _enabled (not yet activated): added `OVERVIEW_V4_QUERY_GEN_MODEL` env var; defaults to `CLAUDE_MODEL`. Set to `claude-haiku-4-5-20251001` to A/B. Trace before vs after to confirm output quality holds._
- [x] **[Q]** Force coverage of a fixed taxonomy (policy positions, voting record, donors, recent news, controversies, accomplishments) — generator picks N queries *per* slot rather than N queries total, so policy/donor topics can't get squeezed out — _shipped (prompt-only, level-1 of taxonomy approach): `query_gen_system.txt` requires ≥2 queries per bucket across 7 buckets. **Taxonomy revised 2026-04-28** based on real-rep trace feedback: dropped "Policy positions" (issue-research pipeline handles that), added **Role/leadership/committees**, reframed accomplishments as **Signature priorities & legislative record** (1–2 known-for issues), tightened controversies to **Substantive controversies** (excludes viral / AI-deepfake / tabloid). See Direction section for full taxonomy + rationale._
- [x] **[Q]** Deduplicate / cluster queries before sending to Tavily (the LLM produced near-duplicates like #5 vs #12, #4 vs #15) — _shipped (exact-match only): `query_generator.py` now dedupes by case/whitespace-normalized form before fan-out. Catches obvious duplicates; near-duplicate clustering (token-overlap similarity) remains a follow-up if real traces still show topical near-duplicates after the new prompt's diversity rules._
- [x] **[Q]** Pass current date into prompt so generator can request `published_date` filters and avoid generic biographical queries for senior incumbents — _partially shipped: `current_date` was already substituted into `query_gen_system.txt`, and the rewritten prompt drops the biographical bucket entirely (which was the wasted slot in the Schumer trace, #16 "Brooklyn career history"). Per-query Tavily date filters remain a follow-up (needs per-query metadata, see breadth_search idea on date filter)._
- [ ] **[Q]** Different query budgets by office level — a US Senator probably wants more national-policy queries; a city councilor wants more local-news queries

## breadth_search

_Observed: 7.6s for 18 queries × 5 results = 90 raw results, fully parallel. Tail latency is the slowest single Tavily call (~1.5–2s)._

_Ideas:_

- [x] **[L]** Use Tavily `search_depth=basic` for breadth (faster) and reserve `advanced` for depth — currently both paths use the same setting — _confirmed already: Tavily SDK default for `search_depth` is `basic`, and `tavily_search_raw` doesn't pass an override. Both breadth and depth currently run on `basic`. If we want depth to use `advanced`, that's a follow-up — the default is correct for breadth's needs._
- [ ] **[L]** Cap concurrency lower to reduce Tavily rate-limit retries (currently `OVERVIEW_V4_SEARCH_CONCURRENCY=5`); evaluate if 8–10 actually returns faster
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
- [x] **[L]** Add an explicit "skip depth" path in triage so a fast structured-output decision can avoid spawning subagents at all — most runs probably don't need depth — _addressed via the prompt rewrite above. The new prompt makes "zero depth calls" the explicit default outcome. (No code change yet — the structured-output skip path remains a follow-up if prompt-level steering proves insufficient.)_
- [x] **[L]** Stream filtered_results to the formatter directly when `OVERVIEW_V4_DEPTH_ENABLED=false` — already supported; benchmark breadth-only vs full to quantify the depth latency tax we're paying for marginal value — _confirmed already shipped: `research_agent.py` short-circuits to empty `depth_search_results` when `OVERVIEW_V4_DEPTH_ENABLED=false`. Benchmarking is the open action — flip the env var in dev and run a few reps. Now that the triage prompt has been reframed to default-no-depth, the gap between the two modes should be smaller anyway._
- [x] **[L]** Move triage to Haiku (it's just picking topics + reasons, not synthesizing) — _enabled (not yet activated): added `OVERVIEW_V4_TRIAGE_MODEL` env var; defaults to `CLAUDE_MODEL`. Set to `claude-haiku-4-5-20251001` to A/B._
- [ ] **[L]** Cap parallel depth subagents to 1–2 (vs. current `OVERVIEW_V4_AGENT_MAX_DEPTH_CALLS=3`) — the staleness use-case rarely needs more than one verification at a time
- [ ] **[L]** Skip the final agent reasoning step (8.6s) — let the formatter consume `breadth + depth` directly. The agent's "summary" before formatter doesn't appear to drive bullet selection
- [x] **[Q]** Pass the current date + rep office level into triage so it can spot staleness signals (e.g. "running for X" vs current date) — _shipped: `current_date` was already substituted into `research_agent_system.txt`. Office level is in the user prompt via `$office`. The new prompt explicitly references `${current_date}` for the "older than 60 days" check._

## depth_subagent

_Observed: each subagent did ~3 LLM calls + ~4 depth_tavily_search calls sequentially. Per-subagent latencies 14.1s, 19.1s, 17.0s (parallel, so the longest is the bottleneck). Depth produced 46 new URLs and ended up driving 55% of final citations — but on topics breadth had already saturated, so it reinforced existing bias rather than filling gaps. Per the "Direction" section above, depth should fire **rarely** to verify potentially-stale facts, not deep-dive on hot topics._

_Ideas:_

- [ ] **[L]** Cap depth recursion lower — `OVERVIEW_V4_DEPTH_RECURSION_LIMIT=8` is generous; 3–4 should suffice for a "verify one fact" use-case
- [x] **[L]** Run depth searches in parallel within a single subagent (currently the agent loop serializes them via the LangGraph react pattern) — _shipped (prompt-only): `depth_agent_system.txt` now explicitly instructs "Issue your queries in parallel in a single tool-use turn — emit 2 or 3 ``depth_tavily_search`` calls together rather than one-at-a-time. This cuts the subagent's wall time roughly in half." Modern Anthropic models do parallel tool-use when prompted; if real traces show serial behavior persisting, fallback is to make depth not a react agent and instead run a fixed-shape parallel fan-out._
- [x] **[L]** Use Haiku for the in-loop reasoning steps — _enabled (not yet activated): added `OVERVIEW_V4_DEPTH_MODEL` env var; defaults to `CLAUDE_MODEL`. Each depth subagent runs ~3 LLM calls in its react loop, so this is leveraged. Set to `claude-haiku-4-5-20251001` to A/B._
- [x] **[Q]** Reshape the subagent prompt around fact-verification: "given this breadth-result claim, find sources confirming or contradicting it as of {current_date}" — instead of the open-ended "research this topic" — _shipped: `depth_agent_system.txt` rewritten as "focused fact-verification agent" with "stay narrow" rules. 2–3 well-targeted queries on the specific factual status, stop early if uncontroversial._
- [ ] **[Q]** Force the subagent to read full Tavily content (`include_raw_content=true`) for at least one promising URL — verification needs the article body, not snippets
- [x] **[Q]** Pass `topic` + `reason` from request_depth into the subagent prompt explicitly so the subagent stays anchored on the verification target rather than drifting — _already shipped before this initiative: `depth_agent_user.txt` already substitutes `$topic` and `$reason`. Marking confirmed._

## formatter

_Observed: **26.0s, in=23.5k tokens, out=1.3k tokens — the second-biggest contributor.** This is where the 90+ search results get distilled to 8 bullets — and where most quality issues land (dropped donors / policy positions / re-election / broader foreign policy)._

_Ideas:_

- [ ] **[L]** Pre-shrink the input pool **without an extra LLM call** — drop snippets to ~200 chars, drop the lowest-relevance half via Python-side ranking in `filter`, blocklist domains. Two sequential LLM calls (curate → format) probably won't beat one big formatter call unless the curate step is on Haiku and the formatter shrinks proportionally — measure before committing
- [x] **[L]** Smaller/faster model for formatter; the shape of work (extract, cite, format) is more pattern-matchy than reasoning-heavy — _enabled (not yet activated): added `OVERVIEW_V4_FORMATTER_MODEL` env var; defaults to `CLAUDE_MODEL`. Set to `claude-haiku-4-5-20251001` to A/B. Highest expected latency win in the doc — formatter is 26s with 23k input tokens._
- [ ] **[L]** Stream the bullets so the user sees the first 1–2 within a few seconds rather than waiting 26s for the full block
- [x] **[Q]** Force coverage of a section taxonomy (e.g. "you must include at least one bullet on policy positions, one on donors if signal exists, one on recent legislative work, one on controversies") — current free-form prompt lets recency-bias eat slots — _shipped (prompt-only): `formatter_system.txt` lists the 7 buckets, asks for 1-3 bullets per bucket where signal exists, skip-entirely if quality bar not met. Mirrors `query_gen_system.txt`. **Revised 2026-04-28**: "Role, leadership & committees" is now an "always include if signal exists" bucket; "Substantive controversies" has explicit exclusions for viral/AI-deepfake/tabloid content; "Signature priorities" replaces broad policy-position survey._
- [x] **[Q]** Allow more bullets when the input is rich — current 5–8 cap is hard, but a US Senator with 60+ results worth covering arguably deserves 10–12 — _shipped: cap raised from 5–8 to 6–12 in `formatter_system.txt`._
- [ ] **[Q]** Make the formatter explicitly emit "no information found" for a topic when results are weak, instead of silently omitting — surfaces gaps to us in traces and to the user as honesty
- [x] **[Q]** Down-rank / strip advocacy + PR domains (DSCC, schumer.senate.gov press releases, House Appropriations releases, YouTube) before the formatter sees them, so it can't lean on them as citations — _shipped: same combination as above (Tavily exclude_domains for DSCC/YouTube; filter_node self-press URL filter for politician PR pages). Formatter never sees these now._
- [x] **[Q]** Audit the date-mixing bug (bullet 4 says "March 2025" inside an otherwise-2026 narrative) — pass `current_date` into the formatter prompt and instruct it to flag/year-tag dates explicitly — _shipped: `current_date` was already passed into `formatter_system.txt` (just not used as a disambiguation rule). Added a strict rule requiring the year to be explicit on every date in a bullet ("in March 2025" not "in March")._
