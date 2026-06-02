# Issue-themed Loading Facts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a rotating "Did you know?" carousel themed to the matched issue while On-the-Issues stance research loads.

**Architecture:** Add a nullable `issue_id` to the existing `facts` table (NULL = general civics fact, today's behavior). `get_civics_facts(issue_id)` returns themed facts, falling back to general when an issue has none. `GET /api/facts?issue=<id>` exposes it. The existing `FactsCarousel` gains an optional `issueId` prop and is rendered in the issue-search loading state.

**Tech Stack:** FastAPI + asyncpg (backend), pytest, React + TypeScript + Vite + TanStack Query (frontend).

**Spec:** `docs/superpowers/specs/2026-06-02-issue-loading-facts-design.md`

**Branch:** `feature/issue-loading-facts`

---

## File Structure

- `backend/schema.sql` — Modify: add `issue_id` column to `facts`; append themed-fact seed rows.
- `backend/db.py:189` — Modify: `get_civics_facts` gains an optional `issue_id` param.
- `backend/routers/facts.py` — Modify: `get_facts` gains an optional `issue` query param.
- `backend/tests/test_get_civics_facts.py` — Modify: cover the issue_id path + fallback (fake pool must accept query args).
- `backend/tests/test_facts_router.py` — Modify: cover the `issue` param passthrough.
- `frontend/src/hooks/useFactsQuery.ts` — Modify: accept optional `issueId`.
- `frontend/src/components/overview/FactsCarousel.tsx` — Modify: accept optional `issueId` prop.
- `frontend/src/components/IssueSearch.tsx` — Modify: render `<FactsCarousel issueId=.../>` in the loading branch.

---

## Task 1: Add `issue_id` column + themed seed facts to schema

**Files:**
- Modify: `backend/schema.sql` (facts table definition + new INSERT block)

This task has no pytest coverage (schema is applied manually, not imported). Verification is a SQL parse check.

- [ ] **Step 1: Add the column to the `facts` table definition**

In `backend/schema.sql`, change the `facts` table (around line 97) to add a nullable issue link after the `text` column:

```sql
CREATE TABLE facts (
    id          SERIAL PRIMARY KEY,
    text        TEXT NOT NULL,
    issue_id    text REFERENCES issues(id),
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Note: `issues` is defined earlier in the file (line ~44), so the FK reference resolves. Existing general-fact `INSERT` rows omit `issue_id`, so they default to `NULL` — unchanged behavior.

- [ ] **Step 2: Append a themed-facts INSERT block**

After the existing general-facts `INSERT INTO facts (text) VALUES (...);` block, add a new block that names both columns. Author **exactly 5 facts per issue** for all 40 issue ids. Use accurate, non-partisan, evergreen civic facts (mechanics, history, numbers — not opinions or current officeholders). Format:

```sql
INSERT INTO facts (text, issue_id) VALUES
  -- abortion
  ('Roe v. Wade was decided by the Supreme Court in 1973 and overturned by Dobbs v. Jackson in 2022.', 'abortion'),
  ('After Dobbs, abortion law is set state-by-state, producing a patchwork of differing rules.', 'abortion'),
  ('The Hyde Amendment, first passed in 1976, bars most federal funding of abortion.', 'abortion'),
  ('Many state abortion laws are written in weeks of gestation, commonly 6, 15, or 24 weeks.', 'abortion'),
  ('Ballot measures in several states since 2022 have let voters decide abortion access directly.', 'abortion'),
  -- affordable_housing
  ('The federal Housing Choice Voucher program (Section 8) helps about 2.3 million households afford rent.', 'affordable_housing'),
  ('"Cost-burdened" is the official term for a household spending over 30% of income on housing.', 'affordable_housing'),
  ('The Low-Income Housing Tax Credit, created in 1986, funds most new affordable units built in the U.S.', 'affordable_housing'),
  ('Zoning rules, set mostly by local governments, heavily shape how much housing can be built.', 'affordable_housing'),
  ('The Fair Housing Act of 1968 made housing discrimination based on race, religion, and more illegal.', 'affordable_housing'),
  -- ... continue for ALL 40 issue ids ...
  ('A fact about water resources.', 'water_resources');
```

**Author 5 facts for each of these 40 issue ids** (do not skip any):
`abortion`, `affordable_housing`, `artificial_intelligence`, `border_security`, `campaign_finance`, `childcare`, `civil_rights`, `climate_change`, `criminal_justice_reform`, `economy`, `education`, `energy_policy`, `environment`, `foreign_policy`, `government_spending`, `gun_control`, `healthcare`, `immigration`, `infrastructure`, `labor_rights`, `lgbtq_rights`, `marijuana_legalization`, `medicare`, `military_veterans`, `minimum_wage`, `national_security`, `police_reform`, `prescription_drug_costs`, `privacy_surveillance`, `public_transportation`, `racial_justice`, `social_security`, `student_debt`, `supreme_court`, `tariffs_trade`, `taxes`, `technology_regulation`, `voting_rights`, `wage_inequality`, `water_resources`.

Quality bar: factual, neutral, timeless, single-sentence, no current officeholder names, no advocacy. Escape apostrophes in SQL by doubling them (`''`).

- [ ] **Step 3: Verify the SQL parses**

Run (from repo root, requires the local Cloud SQL Auth Proxy + `DATABASE_URL`, or any throwaway Postgres):

```bash
psql "$DATABASE_URL" -f backend/schema.sql --set ON_ERROR_STOP=on -o /dev/null && echo "SCHEMA OK"
```

Expected: `SCHEMA OK` (no syntax/FK errors). If no DB is reachable, at minimum run a paren/quote sanity check:

```bash
python3 -c "import re,sys; s=open('backend/schema.sql').read(); print('facts issue rows:', s.count(\"', '\")); print('OK')"
```

Expected: prints a count and `OK`.

- [ ] **Step 4: Commit**

```bash
git add backend/schema.sql
git commit -m "feat: add issue_id to facts table and seed themed facts"
```

---

## Task 2: `get_civics_facts(issue_id)` in db.py

**Files:**
- Modify: `backend/db.py:189`
- Test: `backend/tests/test_get_civics_facts.py`

- [ ] **Step 1: Update the fake pool + write failing tests**

The existing `_FakePool.fetch` takes only `query`; the new code passes a bind arg, so widen it to `*args` and record them. Replace the body of `backend/tests/test_get_civics_facts.py` with:

```python
import asyncio

import db


class _FakePool:
    def __init__(self, rows_by_call):
        # rows_by_call: list of row-lists, returned in call order
        self._rows_by_call = list(rows_by_call)
        self.calls = []  # list of (query, args)

    async def fetch(self, query, *args):
        self.calls.append((query, args))
        return self._rows_by_call.pop(0)


def _patch_pool(monkeypatch, fake):
    async def fake_get_pool():
        return fake
    monkeypatch.setattr(db, "get_pool", fake_get_pool)


def test_general_facts_when_no_issue(monkeypatch):
    fake = _FakePool([[{"text": "Gen one"}, {"text": "Gen two"}]])
    _patch_pool(monkeypatch, fake)

    result = asyncio.run(db.get_civics_facts())

    assert result == ["Gen one", "Gen two"]
    query, args = fake.calls[0]
    assert "issue_id IS NULL" in query
    assert args == ()


def test_themed_facts_when_issue_has_them(monkeypatch):
    fake = _FakePool([[{"text": "Housing fact"}]])
    _patch_pool(monkeypatch, fake)

    result = asyncio.run(db.get_civics_facts("affordable_housing"))

    assert result == ["Housing fact"]
    query, args = fake.calls[0]
    assert "issue_id = $1" in query
    assert args == ("affordable_housing",)
    assert len(fake.calls) == 1  # no fallback query


def test_falls_back_to_general_when_issue_empty(monkeypatch):
    # first call (themed) returns [], second call (general) returns rows
    fake = _FakePool([[], [{"text": "Gen fallback"}]])
    _patch_pool(monkeypatch, fake)

    result = asyncio.run(db.get_civics_facts("artificial_intelligence"))

    assert result == ["Gen fallback"]
    assert len(fake.calls) == 2
    assert "issue_id = $1" in fake.calls[0][0]
    assert "issue_id IS NULL" in fake.calls[1][0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && conda run -n my-reps pytest tests/test_get_civics_facts.py -v`
Expected: FAIL — the current `get_civics_facts` takes no args / query lacks `issue_id`.

- [ ] **Step 3: Implement the issue_id path**

Replace `get_civics_facts` in `backend/db.py` (around line 189):

```python
async def get_civics_facts(issue_id: str | None = None) -> list[str]:
    """Return active facts for the loading carousel, ordered.

    With ``issue_id``, returns that issue's themed facts; if the issue has
    none, falls back to general civics facts (``issue_id IS NULL``) so the
    carousel is never empty. Without ``issue_id``, returns general facts only.
    """
    pool = await get_pool()
    if issue_id:
        rows = await pool.fetch(
            "SELECT text FROM facts WHERE active AND issue_id = $1 ORDER BY id",
            issue_id,
        )
        if rows:
            return [r["text"] for r in rows]
    rows = await pool.fetch(
        "SELECT text FROM facts WHERE active AND issue_id IS NULL ORDER BY id"
    )
    return [r["text"] for r in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && conda run -n my-reps pytest tests/test_get_civics_facts.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/db.py backend/tests/test_get_civics_facts.py
git commit -m "feat: get_civics_facts supports issue-themed facts with general fallback"
```

---

## Task 3: `?issue=` query param on the facts router

**Files:**
- Modify: `backend/routers/facts.py`
- Test: `backend/tests/test_facts_router.py`

- [ ] **Step 1: Write failing tests**

Replace `backend/tests/test_facts_router.py` with:

```python
import asyncio

import routers.facts as facts_router


def test_get_facts_no_issue_passes_none(monkeypatch):
    seen = {}

    async def fake_get_civics_facts(issue_id=None):
        seen["issue_id"] = issue_id
        return ["A", "B"]

    monkeypatch.setattr(facts_router, "get_civics_facts", fake_get_civics_facts)

    resp = asyncio.run(facts_router.get_facts())

    assert resp.facts == ["A", "B"]
    assert seen["issue_id"] is None


def test_get_facts_forwards_issue(monkeypatch):
    seen = {}

    async def fake_get_civics_facts(issue_id=None):
        seen["issue_id"] = issue_id
        return ["Housing"]

    monkeypatch.setattr(facts_router, "get_civics_facts", fake_get_civics_facts)

    resp = asyncio.run(facts_router.get_facts(issue="affordable_housing"))

    assert resp.facts == ["Housing"]
    assert seen["issue_id"] == "affordable_housing"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && conda run -n my-reps pytest tests/test_facts_router.py -v`
Expected: FAIL — `get_facts()` takes no `issue` param.

- [ ] **Step 3: Implement the param**

Edit `backend/routers/facts.py`:

```python
@router.get("/api/facts")
async def get_facts(issue: str | None = None) -> FactsResponse:
    return FactsResponse(facts=await get_civics_facts(issue))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && conda run -n my-reps pytest tests/test_facts_router.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && conda run -n my-reps pytest -q`
Expected: all pass (no regressions in the other 6 test files).

- [ ] **Step 6: Commit**

```bash
git add backend/routers/facts.py backend/tests/test_facts_router.py
git commit -m "feat: facts endpoint accepts optional issue query param"
```

---

## Task 4: Frontend — themed carousel in issue-search loading state

**Files:**
- Modify: `frontend/src/hooks/useFactsQuery.ts`
- Modify: `frontend/src/components/overview/FactsCarousel.tsx`
- Modify: `frontend/src/components/IssueSearch.tsx`

No frontend unit-test harness exists; verification is `npm run build` (type-check + production build) plus a manual smoke check.

- [ ] **Step 1: Add optional `issueId` to `useFactsQuery`**

Replace `frontend/src/hooks/useFactsQuery.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";

const API_URL = import.meta.env.VITE_API_URL;

/**
 * Fetches the loading-carousel facts. With an `issueId`, fetches facts themed
 * to that issue (falling back server-side to general facts if none exist);
 * without one, fetches the general civics facts. Cached per issue for the
 * session (facts don't change while the app is open).
 */
export function useFactsQuery(issueId?: string) {
  return useQuery({
    queryKey: ["facts", issueId ?? "general"],
    queryFn: async (): Promise<string[]> => {
      const url = issueId
        ? `${API_URL}/api/facts?issue=${encodeURIComponent(issueId)}`
        : `${API_URL}/api/facts`;
      const resp = await fetch(url);
      if (!resp.ok) return [];
      const data = await resp.json();
      return (data.facts as string[]) ?? [];
    },
    staleTime: Infinity,
  });
}
```

- [ ] **Step 2: Pass `issueId` through `FactsCarousel`**

In `frontend/src/components/overview/FactsCarousel.tsx`, change the signature to accept an optional prop and forward it. Replace the function declaration line:

```typescript
export function FactsCarousel({ issueId }: { issueId?: string } = {}) {
  const { data: facts } = useFactsQuery(issueId);
```

Leave the rest of the component unchanged.

- [ ] **Step 3: Render the themed carousel in the issue loading state**

In `frontend/src/components/IssueSearch.tsx`:

a) Add the import near the other component imports:

```typescript
import { FactsCarousel } from "@/components/overview/FactsCarousel";
```

b) Give `IssueResult` an `issueId` prop. Update its props type and signature:

```typescript
function IssueResult({
  label,
  issueId,
  items,
  citations,
  furtherReading,
  loading,
}: {
  label: string;
  issueId: string | undefined;
  items: string[] | null;
  citations: Citation[];
  furtherReading: SourceLink[] | undefined;
  loading: boolean;
}) {
```

c) In the loading branch, render the carousel above the skeletons:

```typescript
          {loading && !items ? (
            <div className="space-y-1.5 mt-1">
              <FactsCarousel issueId={issueId} />
              <Skeleton className="h-3.5 w-full" />
              <Skeleton className="h-3.5 w-5/6" />
            </div>
          ) : items ? (
```

d) Pass `issueId` where `IssueResult` is rendered in the `.map`:

```typescript
        <IssueResult
          key={key}
          label={entry.issue?.label ?? "Issue"}
          issueId={entry.issue?.id}
          items={entry.summary?.stance_summary ?? null}
          citations={entry.summary?.citations ?? []}
          furtherReading={entry.summary?.further_reading}
          loading={entry.status === "loading"}
        />
```

- [ ] **Step 4: Type-check and build**

Run: `cd frontend && npm run build`
Expected: build succeeds, no TypeScript errors.

- [ ] **Step 5: Manual smoke check**

With backend + frontend running and the schema applied: search an issue (e.g. "housing") for a rep, confirm the "Did you know?" carousel shows housing-themed facts while loading, then stance bullets replace it on completion. Search an issue you authored facts for and one you didn't (if any) to confirm fallback.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useFactsQuery.ts frontend/src/components/overview/FactsCarousel.tsx frontend/src/components/IssueSearch.tsx
git commit -m "feat: show issue-themed facts carousel while issue stance research loads"
```

---

## Self-Review Notes

- **Spec coverage:** DB column + seed (Task 1), `get_civics_facts(issue_id)` + fallback (Task 2), router param (Task 3), `useFactsQuery`/`FactsCarousel`/`IssueSearch` (Task 4). All spec sections covered.
- **Type consistency:** `get_civics_facts(issue_id: str | None)` used identically in db.py and the router fake; `useFactsQuery(issueId?)` and `FactsCarousel({issueId})` and `IssueResult` `issueId` all `string | undefined`.
- **No-arg behavior preserved:** the overview loader calls `useFactsQuery()` / `<FactsCarousel />` with no args → general facts only, unchanged.
