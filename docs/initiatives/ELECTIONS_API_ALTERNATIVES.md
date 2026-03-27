# Elections API Alternatives

Research into alternatives to Google Civic Information API for upcoming election data. Last updated: 2026-03-25.

## Current State: Google Civic API

Google's Representatives API was turned down in April 2025, but the **Elections and Divisions APIs remain active**. The `voterinfo` endpoint still works but requires a valid `electionId` parameter — without one it returns a 400 "Election unknown" error. Our codebase works around this with a two-step flow (fetch election IDs first via `/elections`, then call `/voterinfo` per ID). The underlying election data comes from the **Voting Information Project (VIP)**, a partnership between Democracy Works and state election officials.

---

## Alternatives

### 1. BallotReady / CivicEngine API

- **URL:** [developers.civicengine.com](https://developers.civicengine.com/docs/api/graphql)
- **Data:** Elections, candidates, ballot measures, elected officials (200k+ records), polling places, early vote locations, ballot drop boxes, voter registration info, district data. Most comprehensive dataset available.
- **Pricing:** Enterprise/custom — contact sales. No public pricing or free tier.
- **API:** GraphQL. Modern, well-documented.
- **Coverage:** Federal, state, and local — down to school board races. Nationwide.
- **Pros:** Most complete single-API replacement. GraphQL returns empty arrays instead of errors (no 400 problem).
- **Cons:** No free tier. B2B product aimed at organizations. Would require rewriting election service layer for GraphQL.

### 2. Democracy Works Elections API

- **URL:** [democracy.works/elections-api](https://www.democracy.works/elections-api)
- **Data:** Election dates, early voting info, registration deadlines, absentee ballot info, polling locations, state voting rules.
- **Pricing:** Custom — contact sales. Nonprofit, so pricing may be more accessible.
- **API:** REST v2 (recently released).
- **Coverage:** Nationwide. Federal through sub-municipal (jurisdictions over 5,000 people).
- **Pros:** This is the **upstream source** for Google Civic's election data (they run the Voting Information Project). Going direct means cutting out the middleman with potentially faster updates.
- **Cons:** No public free tier. API v2 may still be maturing.

### 3. Ballotpedia API

- **URL:** [developer.ballotpedia.org](https://developer.ballotpedia.org)
- **Data:** Candidates (names, party, incumbency, bio, contact, campaign sites), election dates, district maps, officeholders at all levels.
- **Pricing:** Paid subscription. Contact `data@ballotpedia.org`.
- **API:** REST with address-based queries. Good documentation.
- **Coverage:** Federal and state comprehensive. Local coverage in ~30 states for 2026 (AZ, CA, FL, GA, MI, OH, PA, TX, etc.).
- **Pros:** Strong candidate data. Supports geographic queries by address.
- **Cons:** **No polling location or voter registration info** — candidate/race data only. Local coverage has gaps. Candidate lists compiled 2-3 weeks before each election.

### 4. VoteAmerica Civic Data API

- **URL:** [voteamerica.org/civic-data-api](https://www.voteamerica.org/civic-data-api/)
- **Data:** State-specific voting rules, registration deadlines, absentee ballot info, early voting details.
- **Pricing:** Paid — requires "VoteAmericaPlus" subscription.
- **API:** REST v2. Clean docs.
- **Coverage:** All 50 states + DC for voter logistics.
- **Pros:** Clean voter logistics data.
- **Cons:** **No candidate or contest data.** Voter logistics only. Would need to be paired with another API.

### 5. U.S. Vote Foundation Civic Data

- **URL:** [civicdata.usvotefoundation.org](https://civicdata.usvotefoundation.org/)
- **Data:** Election dates/deadlines, state voting requirements, local election official contact info.
- **Pricing:** Licensed. Must be vetted for access.
- **Coverage:** Nationwide for election admin data.
- **Cons:** Election administration data only — no candidates, contests, or ballot measures.

### 6. CTCL Ballot Information Project

- **URL:** [techandciviclife.org](https://www.techandciviclife.org/our-work/civic-information/our-data/ballot-information/)
- **Data:** Candidates, referenda, polling locations, political office descriptions. Address-based ballot queries (similar to Google Civic's `voterInfoQuery`).
- **Pricing:** **Free** for 501(c)(3) nonprofits, small companies, and educational users.
- **API:** JSON API with address-based queries. Contact `ballot@civiclife.org` for access.
- **Coverage:** Nationwide. Their data also feeds into Google Civic API.
- **Pros:** Free for small/nonprofit use. Closest free alternative to Google Civic's address-to-ballot query.
- **Cons:** Not self-serve — must contact for access. Less polished docs. Support/reliability may be limited.

### 7. Open States (Plural Policy)

- **URL:** [docs.openstates.org/api-v3](https://docs.openstates.org/api-v3/)
- **Data:** State legislators, bills, votes, committees.
- **Pricing:** Free/open-source.
- **Coverage:** All 50 states + DC + PR — **state legislatures only**.
- **Not relevant:** This is a legislative tracking API, not an election data API. Only useful for supplementing representative data.

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

## Recommendation

**Stick with Google Civic API for now.** It remains free, active (only the Representatives endpoint was shut down), and the two-step workaround handles the 400-error issue. The data comes from VIP/Democracy Works and CTCL, which are solid sources.

**If Google Civic becomes unreliable or shuts down the Elections endpoint:**

1. **Budget-constrained:** CTCL Ballot Information Project is the closest free alternative. Contact `ballot@civiclife.org`.
2. **Willing to pay:** BallotReady/CivicEngine is the most comprehensive single-API replacement with better error handling.
3. **Middle ground:** Democracy Works is the upstream VIP data provider — same data Google serves, with potentially better support.

**No single free alternative** matches Google Civic's combination of elections + candidates + polling locations + voter info in one self-serve API. A replacement would likely require combining 2 APIs (e.g., Ballotpedia for candidates + CTCL or VoteAmerica for voter logistics).
