# UI Updates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve discoverability of the AI Overview + Issues/Elections tabs, replace level-color confusion with party-color badges, and sort reps by seniority.

**Architecture:** Frontend-only changes in the React/Vite app. No backend or types changes. President/VP already arrive via Cicero (`NATIONAL_EXEC` → `level: "federal"`); the seniority function just sorts them first. One new pure utility (`lib/seniority.ts`), one new component (`CrossLinkCards.tsx`), and edits to three existing files (`RepCard.tsx`, `CandidateCard.tsx`, `RepresentativesPage.tsx`). One new shadcn primitive (`Alert`) added via the official CLI.

**Tech Stack:** React 19 + TypeScript + Vite + Tailwind v4 + shadcn/ui + React Router v7 + lucide-react.

**Verification approach:** This frontend has no test runner installed (no Vitest/Jest). The spec explicitly chose not to add one in this iteration. Each task is verified by **(a) `npx tsc --noEmit`** to catch type errors, **(b) `npm run lint`** to catch style/correctness issues, and **(c) a browser smoke check** of the specific UI affected. Each task ends with a commit.

**Spec:** `docs/superpowers/specs/2026-05-05-ui-updates-design.md`

---

## File Structure

| File | Status | Responsibility |
|------|--------|----------------|
| `frontend/src/lib/seniority.ts` | **new** | Pure ranking + sort function for reps within a level |
| `frontend/src/components/CrossLinkCards.tsx` | **new** | Two CTA cards linking to `/issues` and `/elections` |
| `frontend/src/components/ui/alert.tsx` | **new** (via shadcn CLI) | shadcn Alert primitive used by the helper banner |
| `frontend/src/components/RepCard.tsx` | modify | Promote AI Overview button + caption; replace level badge with party badge |
| `frontend/src/components/CandidateCard.tsx` | modify | Replace level badge with party badge (same helper) |
| `frontend/src/pages/RepresentativesPage.tsx` | modify | Helper banner; apply seniority sort; render CrossLinkCards |

---

## Task 1: Pure seniority ranking utility

**Why first:** zero dependencies on other tasks; everything else can lean on it.

**Files:**
- Create: `frontend/src/lib/seniority.ts`

- [ ] **Step 1: Create the seniority utility**

Create `frontend/src/lib/seniority.ts` with:

```typescript
import type { Representative } from "@/types";

/**
 * Returns a numeric rank for a rep's office string. Lower = more senior.
 * Matching is case-insensitive and uses substring/word checks against the
 * raw `office` text returned by Cicero / the US Congress API.
 *
 * Within a level, ties break alphabetically by last name in `sortBySeniority`.
 */
export function getSeniorityRank(office: string, level: string): number {
  const o = office.toLowerCase();

  if (level === "federal") {
    if (o === "president") return 0;
    if (o.includes("vice president")) return 1;
    // "U.S. Senator", "United States Senator", etc. — but NOT "State Senator"
    if (o.includes("senator") && !o.includes("state")) return 2;
    if (
      (o.includes("representative") || o.includes("congressman") ||
        o.includes("congresswoman") || o.includes("house")) &&
      !o.includes("state")
    ) {
      return 3;
    }
    return 99;
  }

  if (level === "state") {
    if (o.includes("governor") && !o.includes("lieutenant")) return 0;
    if (o.includes("lieutenant governor")) return 1;
    if (o.includes("attorney general")) return 2;
    if (o.includes("secretary of state")) return 3;
    if (
      o.includes("treasurer") || o.includes("comptroller") ||
      o.includes("auditor")
    ) {
      return 4;
    }
    if (o.includes("state senator") || o.includes("state senate")) return 6;
    if (
      o.includes("state representative") || o.includes("state assembly") ||
      o.includes("assembly member") || o.includes("assemblyman") ||
      o.includes("assemblywoman") || o.includes("delegate") ||
      o.includes("state house")
    ) {
      return 7;
    }
    // Other statewide elected (Insurance Commissioner, etc.)
    return 5;
  }

  if (level === "municipal") {
    if (o.includes("mayor")) return 0;
    if (
      o.includes("council") || o.includes("alderman") ||
      o.includes("alderwoman") || o.includes("supervisor") ||
      o.includes("commissioner")
    ) {
      return 2;
    }
    if (
      o.includes("school board") || o.includes("soil") ||
      o.includes("water")
    ) {
      return 3;
    }
    // Other citywide (City Attorney, City Clerk, City Comptroller)
    return 1;
  }

  return 99;
}

function lastName(name: string): string {
  const parts = name.trim().split(/\s+/);
  return (parts[parts.length - 1] || "").toLowerCase();
}

/**
 * Sorts a list of reps in-place-equivalent (returns a new sorted array)
 * by seniority rank, then by last name as a stable tiebreaker.
 */
export function sortBySeniority(reps: Representative[]): Representative[] {
  return [...reps].sort((a, b) => {
    const ra = getSeniorityRank(a.office, a.level);
    const rb = getSeniorityRank(b.office, b.level);
    if (ra !== rb) return ra - rb;
    return lastName(a.name).localeCompare(lastName(b.name));
  });
}
```

- [ ] **Step 2: Typecheck**

Run from `frontend/`:
```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Lint**

Run from `frontend/`:
```bash
npm run lint
```
Expected: no new errors. (Pre-existing warnings, if any, can be ignored — verify the diff did not add new ones.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/seniority.ts
git commit -m "feat(frontend): add seniority ranking utility for reps"
```

---

## Task 2: Apply seniority sort in `RepresentativesPage`

**Files:**
- Modify: `frontend/src/pages/RepresentativesPage.tsx`

- [ ] **Step 1: Wire `sortBySeniority` into `groupByLevel`**

Open `frontend/src/pages/RepresentativesPage.tsx`. Add the import near the top with the other imports:

```typescript
import { sortBySeniority } from "@/lib/seniority";
```

Replace the existing `groupByLevel` function with:

```typescript
function groupByLevel(reps: Representative[]) {
  const groups: { label: string; level: string; reps: Representative[] }[] = [
    { label: "Federal", level: "federal", reps: [] },
    { label: "State", level: "state", reps: [] },
    { label: "Municipal", level: "municipal", reps: [] },
  ];
  for (const rep of reps) {
    const group = groups.find((g) => g.level === rep.level);
    if (group) group.reps.push(rep);
    else groups[2].reps.push(rep);
  }
  return groups
    .filter((g) => g.reps.length > 0)
    .map((g) => ({ ...g, reps: sortBySeniority(g.reps) }));
}
```

- [ ] **Step 2: Typecheck**

```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Lint**

```bash
npm run lint
```
Expected: no new errors.

- [ ] **Step 4: Browser smoke check**

Start the dev server if not running:
```bash
npm run dev
```
Visit `http://localhost:5173`, enter a real address, and verify on `/reps`:
- **Federal:** President first (if returned by Cicero), then VP (if returned), then Senators (alpha by last name), then House Rep.
- **State:** Governor first (if any), down to State Representative.
- **Municipal:** Mayor first (if any), then council members.

If anything looks wrong, fix the matching strings in `seniority.ts` (Task 1 is the place to edit) and reload.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/RepresentativesPage.tsx
git commit -m "feat(frontend): sort reps by seniority within each level"
```

---

## Task 3: Party-badge helper + replace level badge in `RepCard`

**Files:**
- Modify: `frontend/src/components/RepCard.tsx`

- [ ] **Step 1: Edit RepCard — remove level badge, add party badge**

Open `frontend/src/components/RepCard.tsx`. Replace the `levelColors` map and the badge slot inside `CardHeader` as follows.

**Delete** these lines (currently at lines ~22–26):

```typescript
const levelColors: Record<string, string> = {
  federal: "bg-blue-600 text-white hover:bg-blue-700",
  state: "bg-amber-600 text-white hover:bg-amber-700",
  municipal: "bg-emerald-600 text-white hover:bg-emerald-700",
};
```

**Replace with** a party-badge helper:

```typescript
function getPartyBadge(party: string | null): { label: string; className: string } | null {
  if (!party) return null;
  const p = party.trim().toLowerCase();
  if (p === "d" || p.startsWith("democrat")) {
    return { label: "Democrat", className: "bg-blue-600 text-white hover:bg-blue-700" };
  }
  if (p === "r" || p.startsWith("republican")) {
    return { label: "Republican", className: "bg-red-600 text-white hover:bg-red-700" };
  }
  if (p === "i" || p.startsWith("independent")) {
    return { label: "Independent", className: "bg-slate-500 text-white hover:bg-slate-600" };
  }
  return null;
}
```

Then replace the badge JSX inside the header. Find:

```tsx
<div className="flex items-center gap-2 flex-wrap">
  <CardTitle className="text-lg">{rep.name}</CardTitle>
  <Badge className={levelColors[rep.level] || ""}>
    {rep.level}
  </Badge>
</div>
```

Replace with:

```tsx
<div className="flex items-center gap-2 flex-wrap">
  <CardTitle className="text-lg">{rep.name}</CardTitle>
  {(() => {
    const badge = getPartyBadge(rep.party);
    return badge ? <Badge className={badge.className}>{badge.label}</Badge> : null;
  })()}
</div>
```

(The `· {party}` text in `CardDescription` stays — the badge complements it.)

- [ ] **Step 2: Typecheck + lint**

```bash
npx tsc --noEmit && npm run lint
```
Expected: no new errors.

- [ ] **Step 3: Browser smoke check**

On `/reps`, verify:
- Level badge ("federal" / "state" / "municipal") is gone from each card.
- Reps with `party: "Democrat"` show a blue **Democrat** badge.
- Reps with `party: "Republican"` show a red **Republican** badge.
- Reps with no recognized party (e.g., `party: null`, `"Working Families"`) show no badge but still display the party text in the description.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/RepCard.tsx
git commit -m "feat(frontend): replace level badge with party badge on rep cards"
```

---

## Task 4: Apply the same party-badge change in `CandidateCard`

**Files:**
- Modify: `frontend/src/components/CandidateCard.tsx`

- [ ] **Step 1: Mirror the change**

Open `frontend/src/components/CandidateCard.tsx`. **Delete** the `levelColors` constant at the top (lines ~22–26).

Add the same party-badge helper at module scope:

```typescript
function getPartyBadge(party: string | null): { label: string; className: string } | null {
  if (!party) return null;
  const p = party.trim().toLowerCase();
  if (p === "d" || p.startsWith("democrat")) {
    return { label: "Democrat", className: "bg-blue-600 text-white hover:bg-blue-700" };
  }
  if (p === "r" || p.startsWith("republican")) {
    return { label: "Republican", className: "bg-red-600 text-white hover:bg-red-700" };
  }
  if (p === "i" || p.startsWith("independent")) {
    return { label: "Independent", className: "bg-slate-500 text-white hover:bg-slate-600" };
  }
  return null;
}
```

(Note: this duplicates the helper in `RepCard.tsx`. We accept the duplication for now — two ~10-line copies. If a third caller appears, extract to `lib/party.ts`.)

In the JSX, find:

```tsx
<div className="flex items-center gap-2 flex-wrap">
  <CardTitle className="text-lg">{candidate.name}</CardTitle>
  <Badge className={levelColors[candidate.level] || ""}>
    {candidate.level}
  </Badge>
  {candidate.incumbent && (
    <Badge variant="outline">Incumbent</Badge>
  )}
</div>
```

Replace with:

```tsx
<div className="flex items-center gap-2 flex-wrap">
  <CardTitle className="text-lg">{candidate.name}</CardTitle>
  {(() => {
    const badge = getPartyBadge(candidate.party);
    return badge ? <Badge className={badge.className}>{badge.label}</Badge> : null;
  })()}
  {candidate.incumbent && (
    <Badge variant="outline">Incumbent</Badge>
  )}
</div>
```

- [ ] **Step 2: Typecheck + lint**

```bash
npx tsc --noEmit && npm run lint
```
Expected: no new errors.

- [ ] **Step 3: Browser smoke check**

On `/elections`, expand a contest with multiple candidates. Verify:
- No "federal/state/municipal" colored badge on candidate cards.
- Democrats are blue, Republicans are red.
- Incumbent badge still renders when applicable.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/CandidateCard.tsx
git commit -m "feat(frontend): replace level badge with party badge on candidate cards"
```

---

## Task 5: Promote the AI Overview button in `RepCard`

**Files:**
- Modify: `frontend/src/components/RepCard.tsx`

- [ ] **Step 1: Add Sparkles icon import**

In `frontend/src/components/RepCard.tsx`, find the existing lucide-react import:

```typescript
import { ChevronDown, ChevronRight } from "lucide-react";
```

Replace with:

```typescript
import { ChevronDown, ChevronRight, Sparkles } from "lucide-react";
```

- [ ] **Step 2: Promote the button + add caption**

Find the idle-state research block (around line 98–102):

```tsx
{researchStatus === "idle" && (
  <Button onClick={onResearch} variant="outline" className="w-full">
    Generate AI Overview
  </Button>
)}
```

Replace with:

```tsx
{researchStatus === "idle" && (
  <div className="space-y-1">
    <Button onClick={onResearch} className="w-full">
      <Sparkles className="h-4 w-4" />
      Generate AI Overview
    </Button>
    <p className="text-xs text-muted-foreground text-center">
      See their record, accomplishments, and controversies — researched live in ~30 seconds.
    </p>
  </div>
)}
```

The default shadcn `Button` (no `variant`) is the filled/primary style. The icon's `gap` is provided by shadcn's button styles automatically — no extra spacing needed.

- [ ] **Step 3: Typecheck + lint**

```bash
npx tsc --noEmit && npm run lint
```
Expected: no new errors.

- [ ] **Step 4: Browser smoke check**

On `/reps`, verify on a rep that hasn't been researched yet:
- The button is now filled/primary (not outline).
- A small sparkles icon appears to the left of "Generate AI Overview".
- A muted caption sits directly below the button: *"See their record, accomplishments, and controversies — researched live in ~30 seconds."*
- Click the button — research starts as before, button is replaced by skeleton/loading state.
- Once research completes, the caption is gone (it only shows in `idle`).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/RepCard.tsx
git commit -m "feat(frontend): promote AI Overview button + add value-prop caption"
```

---

## Task 6: Add the helper banner above the rep groups

**Files:**
- Create (via shadcn CLI): `frontend/src/components/ui/alert.tsx`
- Modify: `frontend/src/pages/RepresentativesPage.tsx`

- [ ] **Step 1: Install shadcn Alert primitive**

Run from `frontend/`:
```bash
npx shadcn@latest add alert
```

When prompted about overwrites, decline if any of the existing files would be overwritten — only `alert.tsx` should be new.

- [ ] **Step 2: Verify the new file landed**

```bash
ls frontend/src/components/ui/alert.tsx
```
Expected: file exists.

- [ ] **Step 3: Add the banner**

Open `frontend/src/pages/RepresentativesPage.tsx`. Add this import alongside the existing imports:

```typescript
import { Alert, AlertDescription } from "@/components/ui/alert";
```

Find the start of the `hasResults` block:

```tsx
{hasResults && (
  <div className="space-y-8">
    {groups.map((group) => (
```

Replace with (insert the banner as the first child of the `space-y-8` div):

```tsx
{hasResults && (
  <div className="space-y-8">
    <Alert className="max-w-4xl mx-auto">
      <AlertDescription>
        <strong>Tip:</strong> Click "Generate AI Overview" on any rep below to get a live-researched summary of what they've actually been doing in office.
      </AlertDescription>
    </Alert>
    {groups.map((group) => (
```

- [ ] **Step 4: Typecheck + lint**

```bash
npx tsc --noEmit && npm run lint
```
Expected: no new errors.

- [ ] **Step 5: Browser smoke check**

On `/reps`, verify a tip banner appears at the top of the results, above the Federal section, max-width matching the rep groups, with the word "Tip:" bolded.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/RepresentativesPage.tsx frontend/src/components/ui/alert.tsx frontend/components.json
git commit -m "feat(frontend): add tip banner pointing users to AI Overview button"
```

(If `components.json` was not modified, drop it from the `git add`. The `git status` step in the next task will confirm.)

---

## Task 7: Cross-link CTA cards to Issues + Elections

**Files:**
- Create: `frontend/src/components/CrossLinkCards.tsx`
- Modify: `frontend/src/pages/RepresentativesPage.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/CrossLinkCards.tsx`:

```tsx
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface CrossLink {
  to: string;
  title: string;
  body: string;
  cta: string;
}

const LINKS: CrossLink[] = [
  {
    to: "/issues",
    title: "Where do they stand on a specific issue?",
    body: "Search any topic — housing, climate, taxes — and we'll find each rep's stance.",
    cta: "Search by issue",
  },
  {
    to: "/elections",
    title: "What's on your ballot?",
    body: "See upcoming elections, polling info, and candidates for your address.",
    cta: "See upcoming elections",
  },
];

export function CrossLinkCards() {
  return (
    <div className="max-w-4xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-4">
      {LINKS.map((link) => (
        <Link
          key={link.to}
          to={link.to}
          className="block group"
        >
          <Card className="h-full transition-colors hover:border-primary">
            <CardHeader>
              <CardTitle className="text-base">{link.title}</CardTitle>
              <CardDescription>{link.body}</CardDescription>
            </CardHeader>
            <CardContent>
              <span className="inline-flex items-center gap-1 text-sm font-medium text-primary group-hover:underline underline-offset-2">
                {link.cta}
                <ArrowRight className="h-4 w-4" />
              </span>
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Mount it at the bottom of `RepresentativesPage`**

In `frontend/src/pages/RepresentativesPage.tsx`, add the import:

```typescript
import { CrossLinkCards } from "@/components/CrossLinkCards";
```

Find the closing of the `groups.map` block inside the `hasResults` div:

```tsx
    {groups.map((group) => (
      // ... existing group rendering ...
    ))}
  </div>
)}
```

Insert `<CrossLinkCards />` after the `groups.map` and before the closing `</div>`:

```tsx
    {groups.map((group) => (
      // ... existing group rendering ...
    ))}
    <CrossLinkCards />
  </div>
)}
```

- [ ] **Step 3: Typecheck + lint**

```bash
npx tsc --noEmit && npm run lint
```
Expected: no new errors.

- [ ] **Step 4: Browser smoke check**

On `/reps`, scroll to the bottom and verify:
- Two cards render side-by-side on desktop (and stack on mobile — narrow the window to confirm).
- The first links to `/issues` (clicking navigates and the Issues tab becomes active).
- The second links to `/elections` (clicking navigates and the Elections tab becomes active).
- Hover state shows a primary-colored border on the card.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/CrossLinkCards.tsx frontend/src/pages/RepresentativesPage.tsx
git commit -m "feat(frontend): add Issues + Elections cross-link cards on /reps"
```

---

## Final verification

- [ ] **Step 1: Build the frontend**

```bash
cd frontend && npm run build
```
Expected: build succeeds with no errors.

- [ ] **Step 2: End-to-end smoke**

With `npm run dev` running, visit `http://localhost:5173`, enter a known address (e.g., `1600 Pennsylvania Avenue NW, Washington, DC 20500` or your own), and confirm:
- President + VP appear at the top of Federal (if Cicero returns them for that address).
- Senators precede the House Rep.
- Each rep card has a colored party badge instead of a level badge.
- The "Tip" banner is visible above the groups.
- The "Generate AI Overview" button is filled/primary with a sparkles icon and a caption underneath.
- The cross-link cards appear below the last level group.
- Clicking a cross-link card navigates to `/issues` or `/elections` and the corresponding tab is active.

- [ ] **Step 3: Confirm the branch is shippable**

```bash
git -C /Users/andrewbarry/projects/my-representatives log --oneline ui-updates ^main | head -20
```
Expected: a tidy series of commits, one per task above.
