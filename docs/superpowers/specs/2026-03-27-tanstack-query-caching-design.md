# TanStack Query Client-Side Caching

## Problem

When users navigate between `/reps` and `/elections`, component state is lost on unmount. Representatives and elections data re-fetches, and any in-progress or completed AI research summaries disappear. The backend Redis cache prevents redundant AI research, but the user still sees loading spinners on every tab switch.

## Solution

Replace all four custom data-fetching hooks with TanStack Query (`@tanstack/react-query`). TanStack Query's global cache persists data across route changes, deduplicates requests, and provides built-in polling — eliminating the manual `setInterval`/`clearInterval` plumbing in the research hooks.

## Architecture

### New Dependency

- `@tanstack/react-query` — added to frontend
- `@tanstack/react-query-devtools` — dev only (optional, for debugging cache state)

### QueryClient Setup

`QueryClientProvider` wraps the app in `main.tsx` alongside `AddressProvider`. Single `QueryClient` instance created once.

### Hook Replacements

| Current Hook | New Hook | Query Key | Staleness |
|---|---|---|---|
| `useRepresentatives` | `useRepresentativesQuery(address)` | `["representatives", address]` | `staleTime: 5 min` |
| `useElections` | `useElectionsQuery(address)` | `["elections", address]` | `staleTime: 5 min` |
| `useResearch` | `useResearchMutation` + `useResearchQuery(rep)` | `["research", "name\|office"]` | `staleTime: Infinity` when complete |
| `useElectionResearch` | `useElectionResearchQuery(name, date, researchId)` | `["election-research", "name\|date"]` | `staleTime: Infinity` when complete |

### What Stays the Same

- `AddressContext` — unchanged, manages address state and navigation only
- Page components — same structure, consume new hooks with the same return shape
- Backend API — no changes
- `RepCard`, `ElectionCard`, `CandidateCard` — no changes to component interfaces

## Data Flow

### Lookup (reps, elections)

1. User enters address, navigates to `/reps`
2. `useRepresentativesQuery(address)` fires the POST fetch
3. User switches to `/elections` — reps component unmounts, data stays in TanStack Query cache
4. User switches back to `/reps` — cached data renders instantly, no spinner
5. Data is considered fresh for 5 minutes; after that, a background refetch occurs on next mount

### Research (reps)

1. User clicks "Research" — `startResearch` mutation fires POST `/api/research`
2. If response has `status: "complete"` (Redis cache hit), seed the query cache directly — done
3. If `status: "pending"`, activate a polling query with `refetchInterval: 2000`
4. Each poll response updates the cache — partial sections render incrementally (same UX as today)
5. When `status === "complete"`, polling stops (`refetchInterval` returns `false`)
6. Completed research has `staleTime: Infinity` — persists for the entire session

### Research (elections)

Same pattern. `POST /api/elections` returns `research_ids` — for each non-cached ID, a polling query activates immediately.

### Cross-page sharing

Research is keyed by `name|office`. If the same person appears as a rep and a candidate, research done on one page is available on the other — TanStack Query's global cache handles this with no extra code.

### New address

When the user searches a new address, queries with the old address key become inactive. They're garbage-collected after `gcTime` (5 min default).

## Error Handling

No changes to error behavior. TanStack Query surfaces errors via the `error` property on each query, same shape the pages already render. `retry: 1` for lookup queries (handles transient network failures). No retry for research polling (backend manages failure states).

## Verification

Manual testing — no frontend test suite exists:
1. Enter address, verify reps load
2. Switch to elections tab, verify elections load
3. Switch back to reps tab — instant render, no loading spinner
4. Trigger research on a rep, switch tabs while in-progress, switch back — research continues/completes
5. Research a candidate on elections tab, check if same person on reps tab shows the result
