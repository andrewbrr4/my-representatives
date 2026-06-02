# Issue-themed loading facts — design

**Branch:** `feature/issue-loading-facts`
**Date:** 2026-06-02

## Problem

When a user searches "On the Issues" for a representative, the per-issue stance
research runs as a background task and the loading state shows only two skeleton
lines. The general rep-overview loader, by contrast, shows a rotating
"Did you know?" civics-facts carousel (`FactsCarousel`) that makes the wait feel
productive. We want the same treatment for issue search — but with facts themed
to the matched issue (e.g. housing facts for a housing query), not the generic
civics facts.

## Decisions

- **Themed, not generic:** facts are tied to the matched issue.
- **Curated in the DB**, not LLM-generated. Deterministic, zero LLM cost during
  the loading window, full control over content.
- **Safety fallback:** if an issue has no curated facts, fall back to the
  existing general civics facts so the carousel is never empty.

## Architecture

### Database (`backend/schema.sql`)

Add a nullable issue link to the existing `facts` table:

```sql
ALTER TABLE facts ADD COLUMN issue_id text REFERENCES issues(id);
```

- `issue_id IS NULL` → a general civics fact (current rows, unchanged behavior).
- `issue_id = '<id>'` → a fact themed to that issue.

Seed ~5 facts for each of the 40 issues in the taxonomy. Content authored as
part of this work (plain `INSERT INTO facts (text, issue_id) VALUES ...`).
`schema.sql` is the single source of truth (no migration history) — the column
add + seed rows are appended there, and applied once against the DB.

### Data layer (`backend/db.py`)

Extend the existing loader:

```python
async def get_civics_facts(issue_id: str | None = None) -> list[str]:
    pool = await get_pool()
    if issue_id:
        rows = await pool.fetch(
            "SELECT text FROM facts WHERE active AND issue_id = $1 ORDER BY id",
            issue_id,
        )
        if rows:
            return [r["text"] for r in rows]
        # fall through to general facts so the carousel is never empty
    rows = await pool.fetch(
        "SELECT text FROM facts WHERE active AND issue_id IS NULL ORDER BY id",
        # general facts only when no issue_id (or empty issue set)
    )
    return [r["text"] for r in rows]
```

The no-arg call returns **general facts only** (`issue_id IS NULL`) — preserving
today's overview-loader content exactly (it no longer mixes in themed facts).

### Router (`backend/routers/facts.py`)

Add an optional query param:

```python
@router.get("/api/facts")
async def get_facts(issue: str | None = None) -> FactsResponse:
    return FactsResponse(facts=await get_civics_facts(issue))
```

No new endpoint; the existing `GET /api/facts` (no param) is unchanged.

### Frontend

- **`useFactsQuery(issueId?)`** — add an optional `issueId`. Query key becomes
  `["facts", issueId ?? "general"]`; fetches `/api/facts?issue=<id>` when set,
  `/api/facts` otherwise. `staleTime: Infinity` (facts don't change in-session).
- **`FactsCarousel`** — accepts an optional `issueId` prop, passed straight to
  `useFactsQuery`. No other change; it still renders nothing until facts load.
- **`IssueSearch` (`IssueResult`)** — in the loading branch
  (`loading && !items`), render `<FactsCarousel issueId={issueId} />` above the
  existing skeleton lines. `IssueResult` gains an `issueId` prop (the parent
  already has `entry.issue?.id`).

## Data flow

1. User submits an issue query → `issue-match` resolves `issue.id`.
2. Research task spawns; `IssueResult` enters the loading state with `issue.id`.
3. `FactsCarousel` fetches `/api/facts?issue=<id>` → themed facts rotate.
4. On completion, the carousel unmounts and stance bullets render as today.

## Out of scope

- LLM-generated facts.
- Theming the general overview loader (still general civics facts).
- Any change to issue-match or issue-stance research pipelines.

## Testing

- `get_civics_facts(issue_id)` returns themed facts when present; falls back to
  general when the issue has none; no-arg returns general only.
- Router returns themed facts for `?issue=affordable_housing`.
- Frontend: carousel appears in the issue loading state and rotates; build/lint
  clean (`npm run build`).
