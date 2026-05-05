# UI Updates: Discoverability, Color Semantics, Seniority Sort

**Date:** 2026-05-05
**Branch:** `ui-updates`
**Status:** Design — pending implementation

## Problem

User-testing with friends in person surfaced four UX issues on knowmyreps.org:

1. **The AI Overview button is missed.** Users look at the rep cards (name, photo, contact links) and think that's the whole product. They don't notice or try the "Generate AI Overview" button — which is the entire value of the site.
2. **Issues and Elections tabs are missed.** Few users navigate beyond the default `/reps` view.
3. **Level color = party color confusion.** Federal reps get a blue badge, which collides with the well-established mental model that blue = Democrat.
4. **No reasonable rep ordering.** Within a level, reps appear in whatever order the upstream API returns them. Users expect a senior-first ordering (Senator before House Rep, Governor before Assembly Member, Mayor before Council Member, etc.).

## Goals

- Make the AI Overview value obvious at first glance, without auto-spending on research the user didn't ask for.
- Surface Issues + Elections from the `/reps` page where users actually land.
- Stop using level as a color signal. Use color for party affiliation instead, where the mental model already exists.
- Sort reps within a level in a senior-first order users will recognize.

## Non-Goals

- No backend changes. We do not have tenure/seniority data and will not add any. Seniority ordering is purely office-string-based on the frontend.
- No changes to the AI Overview research pipeline (v4) itself.
- No new top-level routes or backend endpoints.
- No copy changes to MISSION.md or other product docs.

## Design

### 1. Make the AI Overview value obvious (`RepCard.tsx`)

Two changes, both in `frontend/src/components/RepCard.tsx`:

- **Promote the button.** Change the `Generate AI Overview` button from `variant="outline"` to the default filled/primary style. Add a `Sparkles` icon from `lucide-react` to the left of the label.
- **Add a one-line value prop directly under the button.** A muted-foreground caption: *"See their record, accomplishments, and controversies — researched live in ~30 seconds."*

The button + caption only shows in the `idle` state (current behavior). Loading/complete/failed states are unchanged.

In addition, on `RepresentativesPage.tsx`, add a **helper banner** above the rep groups:

> Tip: Click "Generate AI Overview" on any rep below to get a live-researched summary of what they've actually been doing in office.

Styling: shadcn `Alert` primitive (add via `npx shadcn@latest add alert` if not present), `max-w-4xl mx-auto`, same horizontal alignment as the level groups. The word "Tip:" is bolded, the rest is normal weight. No emoji. No dismiss state in v1 — if it becomes annoying we can add `localStorage` later.

### 2. Surface Issues + Elections from `/reps`

At the **bottom** of `RepresentativesPage.tsx`, after the level groups, add two side-by-side CTA cards (stacking on mobile):

- **Issue card:** title *"Where do they stand on a specific issue?"*, body *"Search any topic — housing, climate, taxes — and we'll find each rep's stance."*, action: navigates to `/issues`.
- **Elections card:** title *"What's on your ballot?"*, body *"See upcoming elections, polling info, and candidates for your address."*, action: navigates to `/elections`.

Implementation: a new component `frontend/src/components/CrossLinkCards.tsx` that internally uses shadcn `Card` + a `Link` from `react-router-dom`. The whole card is clickable. Hover state gives a subtle border-highlight (existing `hover:border-primary` pattern).

Tab nav (`TabNav.tsx`) is unchanged — the in-context CTAs are the discoverability lever, not a redesigned nav.

### 3. Decouple level from party color

Two changes in `RepCard.tsx`:

- **Remove the colored level badge.** Drop the `levelColors` map and the `<Badge className={levelColors[rep.level]}>` element entirely. The section heading on `RepresentativesPage` already says "Federal" / "State" / "Municipal" — the per-card duplicate carries no extra information.
- **Add a colored party badge** in the same slot next to the rep name:
  - `Democrat` → blue (existing `bg-blue-600 text-white`)
  - `Republican` → red (`bg-red-600 text-white`)
  - `Independent` → neutral gray (`bg-slate-500 text-white`)
  - Anything else (e.g., "Working Families", null) → no badge (we still show the party text in the card description as-is)

The party-badge logic lives in a small helper inside `RepCard.tsx` (or a co-located helper if it grows): `getPartyBadge(party: string | null): { label: string; className: string } | null`. Matching is case-insensitive and accepts both the full name and the single-letter form (`"D"`, `"R"`, `"I"`).

The existing `· {party}` text in `CardDescription` stays — the badge is a visual scan aid, not a replacement.

The same change applies to `CandidateCard.tsx` for symmetry: candidates also have parties and the same color confusion exists. Verify by reading the file during implementation.

### 4. Seniority sort within levels

Pure office-string ranking on the frontend, applied inside `groupByLevel` in `RepresentativesPage.tsx` (or extracted to a sibling helper).

Ranking function `getSeniorityRank(office: string): number` — lower number sorts first. Matching is case-insensitive, uses `includes` / regex on the `office` string, and falls through to a high default rank for unknown offices.

**Federal:**
1. President (exact match `office === "President"`, case-insensitive)
2. Vice President (matches `vice president`)
3. U.S. Senator (matches `senator` and not `state`)
4. U.S. Representative / Congressman / Congresswoman / House (matches `representative` or `house` and not `state`)

President and VP come from Cicero (`district_type: NATIONAL_EXEC`), already mapped to `level: "federal"` — no backend change needed; they just need to sort first.

**State:**
1. Governor (matches `governor` and not `lieutenant`)
2. Lieutenant Governor (matches `lieutenant`)
3. Attorney General
4. Secretary of State
5. State Treasurer / Comptroller / Auditor
6. Other statewide elected (e.g., Insurance Commissioner) — generic catch
7. State Senator (matches `state senator`)
8. State Representative / Assembly Member / Delegate

**Municipal:**
1. Mayor
2. Other citywide elected (City Attorney, City Clerk, Comptroller) — generic catch
3. Council Member / Councilor / Alderman / Supervisor
4. School Board / Soil & Water / other district-level

Within the same rank, sort alphabetically by **last name** (`name.split(" ").slice(-1)[0]`). This is a simple stable tiebreaker — accepts that "Mary Smith Jr." sorts on "Jr." but that's an acceptable edge case.

The function lives in a new file `frontend/src/lib/seniority.ts` and is unit-testable as a pure function. We won't add a test file in v1 unless the project already has frontend tests (it doesn't appear to — verify in implementation).

## Files Touched

- `frontend/src/components/RepCard.tsx` — primary button styling, caption, remove level badge, add party badge
- `frontend/src/components/CandidateCard.tsx` — same party-badge change for symmetry
- `frontend/src/pages/RepresentativesPage.tsx` — helper banner, apply seniority sort, render `CrossLinkCards`
- `frontend/src/components/CrossLinkCards.tsx` — **new**, the two cross-link CTAs
- `frontend/src/lib/seniority.ts` — **new**, pure ranking function

No backend, types, or routing changes.

## Open Questions

None blocking. Marked above where edge cases exist (last-name tiebreaker, unknown party handling).

## Out-of-Scope Followups

- Localstorage-dismissible helper banner.
- Deep-link from a rep card directly into `/issues?rep=...` for that specific rep.
- A11y audit of the new color-coded party badges (text labels mean it's not color-only, but worth a contrast check).
