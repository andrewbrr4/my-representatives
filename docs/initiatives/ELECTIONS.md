# Elections API Alternatives

Research into alternatives to Google Civic Information API for upcoming election data. Last updated: 2026-04-07.

## Current State: Google Civic API

Google's Representatives API was turned down in April 2025, but the **Elections and Divisions APIs remain active**. The `voterinfo` endpoint still works but requires a valid `electionId` parameter — without one it returns a 400 "Election unknown" error. Our codebase works around this with a two-step flow (fetch election IDs first via `/elections`, then call `/voterinfo` per ID). The underlying election data comes from the **Voting Information Project (VIP)**, a partnership between Democracy Works and state election officials.

---

## Alternatives

### ~~1. BallotReady / CivicEngine API~~ — ruled out (enterprise pricing)

- ~~**URL:** [developers.civicengine.com](https://developers.civicengine.com/docs/api/graphql)~~
- ~~**Pricing:** Enterprise/custom — contact sales. No public pricing or free tier.~~
- ~~Most comprehensive dataset but B2B pricing is a non-starter.~~

### ~~2. Democracy Works Elections API~~ — ruled out (enterprise pricing)

- ~~**URL:** [democracy.works/elections-api](https://www.democracy.works/elections-api)~~
- ~~**Pricing:** Custom — contact sales.~~
- ~~Upstream source for Google Civic data, but no free tier.~~

### ~~3. Ballotpedia API~~ — ruled out (enterprise pricing)

- ~~**URL:** [developer.ballotpedia.org](https://developer.ballotpedia.org)~~
- ~~**Pricing:** Paid subscription — API access "thousands/month", one-time CSV from $600.~~
- ~~Good candidate data but no free tier and no polling/voter info.~~

### ~~4. VoteAmerica Civic Data API~~ — ruled out (paid, no election data)

- ~~**URL:** [voteamerica.org/civic-data-api](https://www.voteamerica.org/civic-data-api/)~~
- ~~**Pricing:** Paid "VoteAmericaPlus" subscription.~~
- ~~Voter logistics only — no candidates, contests, or election data.~~

### ~~5. U.S. Vote Foundation Civic Data~~ — ruled out (licensed, admin data only)

- ~~**URL:** [civicdata.usvotefoundation.org](https://civicdata.usvotefoundation.org/)~~
- ~~**Pricing:** Licensed, must be vetted.~~
- ~~Election administration data only — no candidates, contests, or ballot measures.~~

### 6. CTCL Ballot Information Project — **check first before building agent**

- **URL:** [techandciviclife.org](https://www.techandciviclife.org/our-work/research-department/our-data/ballot-information/)
- **Data:** Candidates, referenda, polling locations, political office descriptions. Address-based ballot queries (similar to Google Civic's `voterInfoQuery`).
- **Pricing:** **Free** for 501(c)(3) nonprofits, small companies, and educational users.
- **API:** JSON API with address-based queries. Contact `ballot@civiclife.org` for access.
- **Coverage:** Nationwide. Their data also feeds into Google Civic API.
- **Pros:** Free for small/nonprofit use. Closest free alternative to Google Civic's address-to-ballot query. If coverage is good, could fill gaps without needing an agent at all.
- **Cons:** Not self-serve — must contact for access. Less polished docs. Support/reliability may be limited.
- **Action:** Email `ballot@civiclife.org` to request access and evaluate coverage before investing in agent approach.

### ~~7. Open States (Plural Policy)~~ — ruled out (not election data)

- ~~**URL:** [docs.openstates.org/api-v3](https://docs.openstates.org/api-v3/)~~
- ~~Free, but legislative tracking only — not an election data API.~~

---

## Comparison

| API | Elections | Candidates | Ballot Measures | Polling Locations | Voter Info | Free Tier | Coverage |
|-----|-----------|------------|-----------------|-------------------|------------|-----------|----------|
| **Google Civic** (current) | Yes | Yes | Yes | Yes | Yes | Yes | Nationwide |
| **BallotReady/CivicEngine** | Yes | Yes | Yes | Yes | Yes | No | Nationwide, deep local |
| **Democracy Works** | Yes | Limited | Limited | Yes | Yes | No | Nationwide |
| **Ballotpedia** | Yes | Yes | Yes | No | No | No | Nationwide (local gaps) |
| **VoteAmerica** | No | No | No | No | Yes | No | Nationwide |
| **US Vote Foundation** | Dates only | No | No | No | Yes | No | Nationwide |
| **CTCL Ballot Info Project** | Yes | Yes | Yes | Yes | No | Yes (nonprofit) | Nationwide |
| **Open States** | No | No | No | No | No | Yes | State legislatures only |

---

## Decision: Hybrid Approach (Google Civic + Agent Research)

**Decided 2026-04-07.** Enterprise election APIs (BallotReady, Democracy Works, Ballotpedia) are all priced for B2B orgs — non-starter for this project. Google Civic API remains free but has significant coverage gaps (missing elections, thin ballot data for many addresses).

### Approach

Use a **hybrid model**: keep Google Civic API for what it's good at, and supplement with an AI research agent for election discovery.

**Google Civic API continues to provide:**
- Polling locations, early vote sites, ballot drop-off locations
- Voter registration info and deadlines
- Whatever ballot/contest data it does have

**Agent-based research fills the gaps:**
- Discovering upcoming elections that Google Civic doesn't surface for a given address
- Finding election dates, types, and jurisdictions via web search (Tavily + Claude)
- Structured output parsed into existing `Election`/`Contest`/`Candidate` models

### Open Design Questions

1. **Trigger logic** — Should the agent run every time (in parallel with Google Civic), or only when Google Civic returns thin/no results? Always-on is simpler but costs ~$0.10/lookup.
2. **Data scope** — Should the agent discover just elections (name, date, type) or also attempt candidates and contests? Deeper = less reliable.
3. **Merge/dedup** — When both sources return data, match on election date + type + jurisdiction to avoid duplicates.
4. **Blocking vs. async** — Return Google Civic results immediately and stream in agent-discovered elections via polling? Or block until both complete?

### Cost Estimate

Agent approach uses existing Tavily + Claude infrastructure. Estimated ~$0.05–0.15 per lookup (a few web searches + LLM reasoning), versus $500–5,000+/month for enterprise APIs.

### Next Steps

1. **Email CTCL** (`ballot@civiclife.org`) to request API access — if their coverage fills the gaps, it may be a simpler/more reliable path than the agent approach
2. Create a feature branch for the hybrid work
3. Design the election discovery agent (prompts, structured output, search strategy)
4. Build merge logic for combining Google Civic + agent results
5. Add validation to ensure agent output is reliable (dates, election types, etc.)
