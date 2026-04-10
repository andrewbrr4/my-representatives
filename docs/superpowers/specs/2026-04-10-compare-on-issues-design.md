# Compare on Issues — Design Spec

## Overview

A new page where the user enters a political issue and selects representatives (via checkboxes) to see where each one stands. Results render progressively as each rep's research completes. No backend changes — the existing `issue-match` and `issue-research` endpoints are reused as-is.

Designed to support election candidates in the future. The selection list and result rendering treat subjects generically — initially populated from the user's reps, later extensible to candidates via `Candidate.to_representative()`.

## Routing & Navigation

- **Route:** `/issues`
- **Tab:** Third tab in `TabNav` — "Compare on Issues"
- **Guard:** `RequireAddress` — redirects to `/` if no address (same as `/reps` and `/elections`)
- **Wrapper:** `ResultsLayout` — shared header, address bar, new-search link

## Page Layout (top to bottom)

### 1. Issue Input

Text field at the top. Placeholder: "Enter an issue (e.g. housing, immigration)". Same styling as the existing `IssueSearch.tsx` input.

### 2. Rep Selection List

Sourced from `useRepresentativesQuery(address)` — the same data as the Reps page.

- Grouped by level: Federal, State, Municipal (with group headers)
- Each row: checkbox, rep name, office, party badge (small pill)
- No photos, no contact info — compact
- All unchecked by default (user explicitly opts in to preserve tokens)
- While reps are loading: skeleton placeholder, Compare button disabled

### 3. Compare Button

- Disabled until: issue text is non-empty AND at least one rep is checked
- Label shows count: "Compare (3 selected)"
- During issue classification: disabled, shows "Matching issue..."

### 4. Results Area

Appears below the form after the issue is matched. Shows:

- Header with the matched issue label (e.g. "Housing Affordability")
- Vertical stack of `IssueCompareResult` cards, one per selected rep
- Cards ordered: federal reps first, then state, then municipal (same order as selection list)

## Hook: `useMultiIssueResearch`

Orchestrates the multi-rep issue research flow. Called with no args, returns functions and state.

### `compareIssue(query: string, reps: Representative[])`

1. Fires `POST /api/issue-research` with `{ representative: reps[0], query }` — the backend classifies the issue and starts research for the first rep in one call.
2. If `status: "no_match"` — returns the rejection message. Research does not start.
3. If matched — stores `IssueInfo` (id + label) from the response. The first rep's research is already in progress (polling starts for it). Then fires `POST /api/issue-research` for **each remaining rep in parallel** via `Promise.all` with the same `query`.
4. For each response:
   - `status: "complete"` (cache hit) — writes to TanStack Query cache at `["issue-research", "name|office|issueId"]`
   - `status: "pending"` — starts polling `GET /api/issue-research/{id}` on a 2-second interval

### `getResult(rep: Representative): { status, summary }`

Reads from the TanStack Query cache. Same cache keys as `useIssueSearch` on the Reps page.

### Cache Reuse

Cache keys are `["issue-research", "name|office|issueId"]` — identical to `useIssueSearch`. This means:

- Research triggered on the Reps page shows up instantly here (and vice versa)
- Redis backend cache also deduplicates across sessions
- No redundant research for already-cached rep+issue combos

### Issue Classification Overhead

Each `POST /api/issue-research` call re-runs `match_issue` internally — the backend doesn't expose a "skip classification" option. This is accepted for v1: `match_issue` is cheap (~256 max tokens, no web search). Can be optimized later with an optional `issue_id`/`issue_label` field on the request model.

## Component: `IssueCompareResult`

Per-rep stance result card in the comparison view.

### Header

Rep name, office, party badge (small pill). No photo, no contact info.

### Body

- **Loading:** Skeleton placeholders (2-3 lines)
- **Complete:** Bulleted stance items with inline citations via `renderInline` from `RepCard`
- **Failed:** "Research failed" message with a retry button that re-fires just that rep

### Collapsibility

All results expanded by default (the point is comparison). Each wrapped in `Collapsible` so users can collapse ones they've read.

## State Lifecycle

| State | UI |
|---|---|
| **Initial** | Empty issue input, no reps checked, Compare disabled, results hidden |
| **Ready** | Issue text entered + at least one rep checked. Compare enabled |
| **Matching** | Input/checkboxes disabled. Button shows "Matching issue..." |
| **Researching** | Results area visible. Each card independently shows skeleton → content as its research completes. Progressive fill — no waiting for all to finish |
| **Done** | All cards resolved (complete or failed) |

## Edge Cases

- **No match:** Inline message below input with the rejection text. Form stays editable for retry.
- **Partial failure:** Failed cards show error + retry. Successful cards render normally.
- **New search:** Changing issue and clicking Compare clears previous results, starts fresh. Selected reps persist.
- **Rep list loading:** Skeleton in the rep selection area. Compare disabled.
- **Navigate away and back:** TanStack Query cache preserves results. Form state (selections, issue text) is not restored — but cached results make re-searching instant.

## Files

### New

| File | Purpose |
|---|---|
| `src/pages/IssuesPage.tsx` | Page component: form (issue input + rep checkboxes) + results area |
| `src/hooks/useMultiIssueResearch.ts` | Orchestrates match → fan-out → polling → cache reads/writes |
| `src/components/IssueCompareResult.tsx` | Per-rep stance result card with retry support |

### Modified

| File | Change |
|---|---|
| `src/App.tsx` | Add `/issues` route with `RequireAddress` + `ResultsLayout` |
| `src/components/TabNav.tsx` | Add "Compare on Issues" tab |

### No Changes

- No backend changes
- No changes to existing hooks (`useIssueSearch`, `useResearchQuery`, etc.)
- No changes to existing components on other pages

## Future: Election Candidates

The selection list and result rendering are designed to accept any `Representative`-shaped object. To add candidates:

1. Source candidates from `useElectionsQuery` alongside reps
2. Add a "Candidates" group to the checkbox list (or a separate section)
3. Convert via `Candidate.to_representative()` before passing to the hook
4. Everything else (research, cache, result cards) works unchanged
