# MyReps — Design Approach

This document captures the design thinking, tradeoffs, and open challenges behind MyReps. It's a living document — update it as the product evolves.

For the product vision and principles that inform these decisions, see [MISSION.md](./MISSION.md).

## Overall Design

### Representatives
1. User enters their address.
2. Third-party APIs return a list of representatives at every level of government.
3. The user sees a card for each representative with basic info and a "Learn More" button.
4. When the user clicks "Learn More" on a specific rep, the active overview research pipeline crawls the web to gather information about that representative. The default pipeline (LangGraph breadth + adaptive depth + formatter) lives at `backend/research/overview/`; legacy variants `v1` / `v2` / `v3` are kept under `backend/research/overview/legacy/` and selectable via `OVERVIEW_PIPELINE_VERSION`; see [rep-overview-versions.md](./rep-overview-versions.md) for the architecture of each.
5. Rendering depends on the version:
   - **Default**: a single distilled bullet list renders once the formatter completes (no per-section streaming).
   - **Legacy `v1`**: results stream into the card section-by-section as each of 5 parallel agents completes. Sections are revealed in display order — a section stays as a skeleton placeholder until all preceding sections are complete, so the user always sees a clean top-down fill.
   - **Legacy `v2` / `v3`**: like the default — a single distilled bullet list once synthesis/distillation completes.

Research is **on-demand** — only triggered for reps the user explicitly wants to learn about. This cuts API costs ~80%+ compared to researching every rep on every lookup, since most users only care about a few of their ~15+ representatives.

### Elections
1. User switches to the Elections tab (available after entering an address).
2. The backend calls the Google Civic Information API (`voterinfo` endpoint) with the user's address to discover upcoming elections, ballot contests, candidates, and voter info.
3. Up to 3 elections are automatically researched via the election research pipeline (1 section: ballot overview via sync LLM call).
4. Each election card shows AI-generated context, voter info (registration links, absentee info, early voting sites, drop-off locations), and ballot contests with candidates.
5. Candidates can be individually researched using the same on-demand representative research pipeline (including ordered section rendering).

The election research pipeline is lighter than rep research — 1 section (ballot overview) vs 5, with no web search needed. Election research is cached per election+address combination.

### Issue Search
1. From the Representatives tab, users can search for an issue (e.g., "housing affordability") to see how their reps relate to it.
2. The backend first validates the issue via an LLM match call, then runs a research agent to find each rep's stance on the issue.
3. Results are polled and displayed per-rep, same as other research flows.

## Summary Card Content

Agentic coding via Claude Code makes the technical aspects of building the functionality quite smooth. The true challenge of this project lies in the design of the product itself — specifically, crafting the content of the summary cards. For now, we are more focused on optimizing this content than the visual UI components such as color, font, etc.

The content in these cards is ultimately determined by the prompts given to the active overview pipeline under [`backend/research/overview/`](../backend/research/overview/) and the Pydantic models used to structure the data. The default pipeline's prompts live in `research/overview/prompts/`; each legacy variant owns its own under `research/overview/legacy/vN/prompts/`.

### Challenges

Crafting these cards is not easy. We need to strike several difficult balances:

- **Comprehensive information vs. conciseness** — give people enough to be useful without overwhelming them.
- **No PR spin, but still nonpartisan** — cut through talking points and present substance, without editorializing or taking sides.
- **Government speak vs. real-world impact** — translate policy language into plain terms so people can understand what actually affects them.

### Current Card Sections

The card output format depends on `OVERVIEW_PIPELINE_VERSION`:

**Legacy `v1` — five sections**, each a bulleted list with per-section citations:

| Section | Description | Format |
|---------|-------------|--------|
| **Policy Positions** | Where the representative stands on key issues, based on their voting record and public statements rather than campaign messaging. | Bulleted list |
| **Recent Legislative Record** | Key legislative measures they recently supported or opposed. | Bulleted list |
| **Accomplishments** | Notable achievements, successful initiatives, awards, and bipartisan wins. | Bulleted list |
| **Controversies** | Scandals, ethics complaints, controversial votes or statements, lawsuits, and public criticism. | Bulleted list |
| **Top Donors** | List of the representative's largest political donors, five max. | Bulleted list |

**Default and legacy `v2` / `v3` — a single blended bullet list** (6–8 bullets in the default, 5–8 in legacy) with a unified citation pool and inline `[N]` markers. The default derives this from a LangGraph breadth+depth flow; legacy `v2` from five section agents via a synthesis step; legacy `v3` from a breadth-first search fan-out and a single distillation. See [rep-overview-versions.md](./rep-overview-versions.md).

### Election Card Sections

Election research uses a lighter 1-section pipeline:

| Section | Description | Format |
|---------|-------------|--------|
| **Ballot Overview** | Explains what's on the ballot — contests, candidates, ballot measures — and why they matter. Generated from LLM training data (no web search). | Paragraph-style text |
