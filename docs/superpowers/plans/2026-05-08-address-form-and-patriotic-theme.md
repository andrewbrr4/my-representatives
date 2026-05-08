# Structured Address Form + Federalist Theme — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-field address autocomplete with a structured 4-field form (Street with Google Places autocomplete, City, State dropdown, ZIP) and apply a Federalist patriotic visual refresh (ivory/navy/oxblood palette, Source Serif 4 + Inter typography, recolored party badges, navy-star favicon).

**Architecture:** Frontend-only. Backend contract unchanged (concatenated address string still flows to `/api/representatives` and `/api/elections`). Theme uses CSS custom properties via Tailwind v4's `@theme inline` block. Fonts self-hosted via `@fontsource`. Place Details (a second Google Places call) populates the structured fields after a suggestion is picked.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind v4, shadcn/ui (new-york style, Radix-backed), TanStack Query, react-router-dom 7, Google Places API (Places API New).

**Spec:** [`docs/superpowers/specs/2026-05-08-address-form-and-patriotic-theme-design.md`](../specs/2026-05-08-address-form-and-patriotic-theme-design.md)

**Branch:** `address-form-federalist-theme` (already created; spec already committed)

**Working directory:** `/Users/andrewbarry/projects/my-representatives` — frontend lives at `frontend/`. Run `npm` commands from `frontend/`.

---

## File Structure

| File | New / Modify | Responsibility |
|---|---|---|
| `frontend/src/index.css` | Modify | Federalist palette tokens + party-color tokens + `@theme inline` mappings + `@layer base` font-family rules |
| `frontend/src/main.tsx` | Modify | `@fontsource` imports |
| `frontend/index.html` | Modify | Favicon href |
| `frontend/public/star.svg` | New | Navy 5-point star favicon |
| `frontend/public/vite.svg` | Delete | Default Vite favicon |
| `frontend/src/lib/partyBadge.ts` | New | Shared party badge label+className util |
| `frontend/src/lib/usStates.ts` | New | Static list of 50 states + DC |
| `frontend/src/components/ui/select.tsx` | New (generated) | shadcn Select component |
| `frontend/src/hooks/useAddressAutocomplete.ts` | Modify | Surface `placeId`, add `fetchPlaceDetails` |
| `frontend/src/components/AddressSearch.tsx` | Modify (rewrite) | Four-field form |
| `frontend/src/components/RepCard.tsx` | Modify | Use shared `getPartyBadge` |
| `frontend/src/components/CandidateCard.tsx` | Modify | Use shared `getPartyBadge` |
| `frontend/src/components/IssueCompareResult.tsx` | Modify | Use shared `getPartyBadge` |
| `frontend/src/pages/SearchPage.tsx` | Modify | Bump h1 size to `text-5xl` |
| `frontend/src/pages/RepresentativesPage.tsx` | Modify | Bump group label to `text-2xl` |
| `frontend/package.json`, `package-lock.json` | Modify | Add `@fontsource/inter`, `@fontsource/source-serif-4` |

**Note on testing:** This is a frontend-only design refresh. The codebase has no Vitest/Jest setup currently. Verification is via manual UI checks plus `npm run build` (typecheck + bundle) and `npm run lint`. Each task ends with one or more of those automated commands so regressions surface immediately.

---

## Task 1: Apply Federalist palette to `index.css`

**Files:**
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Replace the `:root` block with Federalist tokens**

Open `frontend/src/index.css`. Replace the entire `:root { … }` block (currently lines 49–82) with:

```css
:root {
    --radius: 0.625rem;
    --background: oklch(0.97 0.012 85);
    --foreground: oklch(0.22 0.06 255);
    --card: oklch(0.99 0.008 85);
    --card-foreground: oklch(0.22 0.06 255);
    --popover: oklch(0.99 0.008 85);
    --popover-foreground: oklch(0.22 0.06 255);
    --primary: oklch(0.30 0.10 255);
    --primary-foreground: oklch(0.97 0.012 85);
    --secondary: oklch(0.93 0.014 85);
    --secondary-foreground: oklch(0.30 0.10 255);
    --muted: oklch(0.93 0.014 85);
    --muted-foreground: oklch(0.48 0.04 255);
    --accent: oklch(0.40 0.15 25);
    --accent-foreground: oklch(0.97 0.012 85);
    --destructive: oklch(0.577 0.245 27.325);
    --border: oklch(0.86 0.014 85);
    --input: oklch(0.86 0.014 85);
    --ring: oklch(0.30 0.10 255);
    --chart-1: oklch(0.30 0.10 255);
    --chart-2: oklch(0.40 0.15 25);
    --chart-3: oklch(0.55 0.02 85);
    --chart-4: oklch(0.48 0.04 255);
    --chart-5: oklch(0.70 0.05 85);
    --sidebar: oklch(0.97 0.012 85);
    --sidebar-foreground: oklch(0.22 0.06 255);
    --sidebar-primary: oklch(0.30 0.10 255);
    --sidebar-primary-foreground: oklch(0.97 0.012 85);
    --sidebar-accent: oklch(0.93 0.014 85);
    --sidebar-accent-foreground: oklch(0.30 0.10 255);
    --sidebar-border: oklch(0.86 0.014 85);
    --sidebar-ring: oklch(0.30 0.10 255);
    --party-democrat: oklch(0.30 0.10 255);
    --party-republican: oklch(0.40 0.15 25);
    --party-independent: oklch(0.55 0.02 85);
}
```

- [ ] **Step 2: Replace the `.dark` block with Federalist dark tokens**

Replace the entire `.dark { … }` block with:

```css
.dark {
    --background: oklch(0.18 0.05 255);
    --foreground: oklch(0.94 0.012 85);
    --card: oklch(0.23 0.06 255);
    --card-foreground: oklch(0.94 0.012 85);
    --popover: oklch(0.23 0.06 255);
    --popover-foreground: oklch(0.94 0.012 85);
    --primary: oklch(0.85 0.06 85);
    --primary-foreground: oklch(0.18 0.05 255);
    --secondary: oklch(0.28 0.05 255);
    --secondary-foreground: oklch(0.94 0.012 85);
    --muted: oklch(0.28 0.05 255);
    --muted-foreground: oklch(0.72 0.04 85);
    --accent: oklch(0.55 0.18 25);
    --accent-foreground: oklch(0.94 0.012 85);
    --destructive: oklch(0.704 0.191 22.216);
    --border: oklch(1 0 0 / 12%);
    --input: oklch(1 0 0 / 15%);
    --ring: oklch(0.85 0.06 85);
    --chart-1: oklch(0.55 0.10 255);
    --chart-2: oklch(0.55 0.18 25);
    --chart-3: oklch(0.62 0.02 85);
    --chart-4: oklch(0.72 0.04 85);
    --chart-5: oklch(0.85 0.06 85);
    --sidebar: oklch(0.23 0.06 255);
    --sidebar-foreground: oklch(0.94 0.012 85);
    --sidebar-primary: oklch(0.85 0.06 85);
    --sidebar-primary-foreground: oklch(0.18 0.05 255);
    --sidebar-accent: oklch(0.28 0.05 255);
    --sidebar-accent-foreground: oklch(0.94 0.012 85);
    --sidebar-border: oklch(1 0 0 / 12%);
    --sidebar-ring: oklch(0.85 0.06 85);
    --party-democrat: oklch(0.55 0.10 255);
    --party-republican: oklch(0.55 0.18 25);
    --party-independent: oklch(0.62 0.02 85);
}
```

- [ ] **Step 3: Add party color mappings to `@theme inline`**

Inside the existing `@theme inline { … }` block (around lines 8–47), append these three lines just before the closing brace:

```css
    --color-party-democrat: var(--party-democrat);
    --color-party-republican: var(--party-republican);
    --color-party-independent: var(--party-independent);
```

- [ ] **Step 4: Build to verify CSS is valid**

Run from `frontend/`:
```bash
npm run build
```
Expected: build succeeds (`vite build` produces `dist/` without CSS errors). If it fails, the most likely cause is a typo in a token value — re-check the substituted blocks.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/index.css
git commit -m "feat(theme): apply federalist palette tokens"
```

---

## Task 2: Self-host Source Serif 4 + Inter via @fontsource

**Files:**
- Modify: `frontend/package.json`, `frontend/package-lock.json`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Install fontsource packages**

Run from `frontend/`:
```bash
npm install @fontsource/inter @fontsource/source-serif-4
```
Expected: both packages added to `package.json` `dependencies`, `package-lock.json` updated, `node_modules/@fontsource/{inter,source-serif-4}` populated.

- [ ] **Step 2: Import only the weights we use into `main.tsx`**

Open `frontend/src/main.tsx`. Add these five imports between the existing `import "./index.css";` line and the `import App from "./App.tsx";` line (or after the `./index.css` import — order between css and font imports is not load-bearing here because index.css references the families by name and the font @font-face declarations register globally):

```ts
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/source-serif-4/600.css";
import "@fontsource/source-serif-4/700.css";
```

The full import block should now look like:
```ts
import "./index.css";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/source-serif-4/600.css";
import "@fontsource/source-serif-4/700.css";
import App from "./App.tsx";
```

- [ ] **Step 3: Apply the font families in `index.css`**

Open `frontend/src/index.css`. Replace the existing `@layer base { … }` block (currently the last block, around lines 118–125) with:

```css
@layer base {
  * {
    @apply border-border outline-ring/50;
    }
  body {
    @apply bg-background text-foreground;
    font-family: "Inter", ui-sans-serif, system-ui, sans-serif;
    }
  h1, h2, h3, .font-display {
    font-family: "Source Serif 4", ui-serif, Georgia, serif;
    }
}
```

- [ ] **Step 4: Build to verify font wiring is valid**

Run from `frontend/`:
```bash
npm run build
```
Expected: build succeeds. The `@fontsource` packages emit `.woff2` files into the bundle; vite handles them automatically.

- [ ] **Step 5: Manual check — start dev server and view a page**

Run from `frontend/`:
```bash
npm run dev
```
Open http://localhost:5173 in a browser. The "KnowMyReps" h1 on the landing page should render in Source Serif 4 (a slightly contrasted serif). The body paragraphs below should render in Inter (geometric sans). Stop the dev server with Ctrl-C.

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/main.tsx frontend/src/index.css
git commit -m "feat(theme): self-host Source Serif 4 and Inter via fontsource"
```

---

## Task 3: Replace Vite favicon with navy star

**Files:**
- Create: `frontend/public/star.svg`
- Delete: `frontend/public/vite.svg`
- Modify: `frontend/index.html`

- [ ] **Step 1: Create `frontend/public/star.svg`**

Write file `frontend/public/star.svg` with exactly this content:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <path d="M16 2 L19.6 12.4 L30.5 12.4 L21.6 19 L25.2 29.4 L16 22.8 L6.8 29.4 L10.4 19 L1.5 12.4 L12.4 12.4 Z" fill="#0E2D4F"/>
</svg>
```

- [ ] **Step 2: Update `index.html` favicon link**

Open `frontend/index.html`. Change the line:
```html
<link rel="icon" type="image/svg+xml" href="/vite.svg" />
```
to:
```html
<link rel="icon" type="image/svg+xml" href="/star.svg" />
```

- [ ] **Step 3: Delete the old Vite favicon**

```bash
rm frontend/public/vite.svg
```

- [ ] **Step 4: Build to verify the new asset is bundled**

Run from `frontend/`:
```bash
npm run build
```
Expected: build succeeds; `dist/star.svg` exists; `dist/vite.svg` does not.

- [ ] **Step 5: Manual check — start dev server and inspect tab icon**

Run from `frontend/`:
```bash
npm run dev
```
Open http://localhost:5173. The browser tab should show a navy 5-point star instead of the purple Vite logo. Stop the dev server.

- [ ] **Step 6: Commit**

```bash
git add frontend/public/star.svg frontend/index.html
git rm frontend/public/vite.svg
git commit -m "feat(theme): replace vite favicon with navy star"
```

---

## Task 4: Extract shared `getPartyBadge` util

**Files:**
- Create: `frontend/src/lib/partyBadge.ts`
- Modify: `frontend/src/components/RepCard.tsx`
- Modify: `frontend/src/components/CandidateCard.tsx`
- Modify: `frontend/src/components/IssueCompareResult.tsx`

- [ ] **Step 1: Create the shared util**

Write file `frontend/src/lib/partyBadge.ts`:

```ts
export type PartyBadge = { label: string; className: string };

export function getPartyBadge(party: string | null): PartyBadge | null {
  if (!party) return null;
  const p = party.trim().toLowerCase();
  if (p === "d" || p.startsWith("democrat")) {
    // Match the input form so the badge doesn't say "Democrat" while the
    // CardDescription says "· Democratic" on the same card.
    const label = p.startsWith("democratic") ? "Democratic" : "Democrat";
    return {
      label,
      className: "bg-party-democrat text-primary-foreground hover:bg-party-democrat/90",
    };
  }
  if (p === "r" || p.startsWith("republican")) {
    return {
      label: "Republican",
      className: "bg-party-republican text-primary-foreground hover:bg-party-republican/90",
    };
  }
  if (p === "i" || p.startsWith("independent")) {
    return {
      label: "Independent",
      className: "bg-party-independent text-primary-foreground hover:bg-party-independent/90",
    };
  }
  return null;
}
```

- [ ] **Step 2: Replace the inline copy in `RepCard.tsx`**

Open `frontend/src/components/RepCard.tsx`. Delete the local `getPartyBadge` function (lines 22–38). Add this import to the top of the file (next to the other `@/lib/...` imports if any, or near the bottom of the imports block):

```ts
import { getPartyBadge } from "@/lib/partyBadge";
```

- [ ] **Step 3: Replace the inline copy in `CandidateCard.tsx`**

Open `frontend/src/components/CandidateCard.tsx`. Delete the local `getPartyBadge` function (around lines 23–39). Add the same import:

```ts
import { getPartyBadge } from "@/lib/partyBadge";
```

- [ ] **Step 4: Replace the inline copy in `IssueCompareResult.tsx`**

Open `frontend/src/components/IssueCompareResult.tsx`. Delete the local `getPartyBadge` function (the function defined near the top). Add the same import:

```ts
import { getPartyBadge } from "@/lib/partyBadge";
```

- [ ] **Step 5: Type-check and build**

Run from `frontend/`:
```bash
npx tsc --noEmit && npm run lint && npm run build
```
Expected: all three commands succeed. If `tsc` complains, the most likely cause is a missing import or a leftover orphaned reference to the deleted local function.

- [ ] **Step 6: Manual check — verify badges look right**

Run from `frontend/`:
```bash
npm run dev
```
Enter an address that returns reps from both parties (e.g., `1600 Pennsylvania Ave NW, Washington, DC 20500` after Task 8 ships, or any current valid address). Visually verify:
- Democrat badges render with a soft navy fill (the new `--party-democrat`), not bright `bg-blue-600`.
- Republican badges render with a soft oxblood fill (the new `--party-republican`), not bright `bg-red-600`.
- Independent badges render warm gray.

Stop the dev server.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/partyBadge.ts frontend/src/components/RepCard.tsx frontend/src/components/CandidateCard.tsx frontend/src/components/IssueCompareResult.tsx
git commit -m "refactor(party): extract shared getPartyBadge with theme tokens"
```

---

## Task 5: Page-level heading size bumps

**Files:**
- Modify: `frontend/src/pages/SearchPage.tsx`
- Modify: `frontend/src/pages/RepresentativesPage.tsx`
- Modify: `frontend/src/components/RepCard.tsx`
- Modify: `frontend/src/components/CandidateCard.tsx`

- [ ] **Step 1: Bump the SearchPage h1**

Open `frontend/src/pages/SearchPage.tsx`. Find the line:
```tsx
<h1 className="text-4xl font-bold tracking-tight mb-2">KnowMyReps</h1>
```
Change to:
```tsx
<h1 className="text-5xl font-bold tracking-tight mb-2">KnowMyReps</h1>
```

- [ ] **Step 2: Bump the group label h2 in RepresentativesPage**

Open `frontend/src/pages/RepresentativesPage.tsx`. Find:
```tsx
<h2 className="text-xl font-semibold">
  {group.label}
</h2>
```
Change to:
```tsx
<h2 className="text-2xl font-semibold">
  {group.label}
</h2>
```

- [ ] **Step 3: Verify CardTitle renders as a heading element so serif inherits**

Open `frontend/src/components/ui/card.tsx` (read-only inspection). If `CardTitle` renders as a `<div>` (the shadcn default), add `as="h3"` props in the two card components, or wrap the title content in an explicit `<h3>` inside `<CardTitle>`. If `CardTitle` already renders as a heading, skip this step.

If you need to wrap: change in `RepCard.tsx`:
```tsx
<CardTitle className="text-lg">{rep.name}</CardTitle>
```
to:
```tsx
<CardTitle className="text-xl font-semibold"><h3 className="contents">{rep.name}</h3></CardTitle>
```
And the same shape change in `CandidateCard.tsx`. Note: if the shadcn version renders `CardTitle` as `<h3>` natively, just bump the className: `className="text-xl font-semibold"`.

- [ ] **Step 4: Bump the CardTitle size in RepCard and CandidateCard**

In both files, change:
```tsx
<CardTitle className="text-lg">
```
to:
```tsx
<CardTitle className="text-xl font-semibold">
```

(Combine with the wrap from Step 3 if needed.)

- [ ] **Step 5: Type-check and build**

Run from `frontend/`:
```bash
npx tsc --noEmit && npm run build
```
Expected: success.

- [ ] **Step 6: Manual check — typography hierarchy**

Run `npm run dev`. Verify:
- `KnowMyReps` h1 on landing page is large, serif, bold.
- "Federal" / "State" / "Municipal" group labels on `/reps` are mid-size, serif.
- Each rep's name on a card is mid-size, serif.
- Body copy and `CardDescription` lines render in Inter.

Stop the dev server.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/SearchPage.tsx frontend/src/pages/RepresentativesPage.tsx frontend/src/components/RepCard.tsx frontend/src/components/CandidateCard.tsx
git commit -m "feat(theme): bump heading sizes for serif hierarchy"
```

---

## Task 6: Add the static US states list

**Files:**
- Create: `frontend/src/lib/usStates.ts`

- [ ] **Step 1: Create the file**

Write file `frontend/src/lib/usStates.ts`:

```ts
export type UsState = { code: string; name: string };

export const US_STATES: ReadonlyArray<UsState> = [
  { code: "AL", name: "Alabama" },
  { code: "AK", name: "Alaska" },
  { code: "AZ", name: "Arizona" },
  { code: "AR", name: "Arkansas" },
  { code: "CA", name: "California" },
  { code: "CO", name: "Colorado" },
  { code: "CT", name: "Connecticut" },
  { code: "DE", name: "Delaware" },
  { code: "DC", name: "District of Columbia" },
  { code: "FL", name: "Florida" },
  { code: "GA", name: "Georgia" },
  { code: "HI", name: "Hawaii" },
  { code: "ID", name: "Idaho" },
  { code: "IL", name: "Illinois" },
  { code: "IN", name: "Indiana" },
  { code: "IA", name: "Iowa" },
  { code: "KS", name: "Kansas" },
  { code: "KY", name: "Kentucky" },
  { code: "LA", name: "Louisiana" },
  { code: "ME", name: "Maine" },
  { code: "MD", name: "Maryland" },
  { code: "MA", name: "Massachusetts" },
  { code: "MI", name: "Michigan" },
  { code: "MN", name: "Minnesota" },
  { code: "MS", name: "Mississippi" },
  { code: "MO", name: "Missouri" },
  { code: "MT", name: "Montana" },
  { code: "NE", name: "Nebraska" },
  { code: "NV", name: "Nevada" },
  { code: "NH", name: "New Hampshire" },
  { code: "NJ", name: "New Jersey" },
  { code: "NM", name: "New Mexico" },
  { code: "NY", name: "New York" },
  { code: "NC", name: "North Carolina" },
  { code: "ND", name: "North Dakota" },
  { code: "OH", name: "Ohio" },
  { code: "OK", name: "Oklahoma" },
  { code: "OR", name: "Oregon" },
  { code: "PA", name: "Pennsylvania" },
  { code: "RI", name: "Rhode Island" },
  { code: "SC", name: "South Carolina" },
  { code: "SD", name: "South Dakota" },
  { code: "TN", name: "Tennessee" },
  { code: "TX", name: "Texas" },
  { code: "UT", name: "Utah" },
  { code: "VT", name: "Vermont" },
  { code: "VA", name: "Virginia" },
  { code: "WA", name: "Washington" },
  { code: "WV", name: "West Virginia" },
  { code: "WI", name: "Wisconsin" },
  { code: "WY", name: "Wyoming" },
];
```

- [ ] **Step 2: Type-check**

Run from `frontend/`:
```bash
npx tsc --noEmit
```
Expected: success.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/usStates.ts
git commit -m "feat(address): add US states list"
```

---

## Task 7: Add shadcn Select component

**Files:**
- Create: `frontend/src/components/ui/select.tsx` (generated by shadcn CLI)

- [ ] **Step 1: Generate the component**

Run from `frontend/`:
```bash
npx shadcn@latest add select
```

Expected: prompts may ask to confirm creation; accept defaults. The CLI writes `src/components/ui/select.tsx`. If it asks about overwriting unrelated files, choose "no" — only `select.tsx` should be new.

If a `radix-ui` dependency notice appears, it should be a no-op since `radix-ui` is already in `package.json`.

- [ ] **Step 2: Verify the component compiles**

Run from `frontend/`:
```bash
npx tsc --noEmit && npm run lint
```
Expected: success.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/select.tsx
git commit -m "feat(ui): add shadcn Select component"
```

If the CLI also touched `package.json` / `package-lock.json` (adding a Radix Select package), include them in the same commit:
```bash
git add frontend/package.json frontend/package-lock.json
git commit --amend --no-edit
```

---

## Task 8: Extend `useAddressAutocomplete` with `placeId` + `fetchPlaceDetails`

**Files:**
- Modify: `frontend/src/hooks/useAddressAutocomplete.ts`

- [ ] **Step 1: Replace the hook with the extended version**

Open `frontend/src/hooks/useAddressAutocomplete.ts` and replace the entire file contents with:

```ts
import { useState, useRef, useCallback, useEffect } from "react";

interface PlaceSuggestion {
  mainText: string;
  secondaryText: string;
  fullText: string;
  placeId: string;
}

export interface AddressComponents {
  street: string;
  city: string;
  state: string;
  zip: string;
}

const PLACES_AUTOCOMPLETE_URL =
  "https://places.googleapis.com/v1/places:autocomplete";
const PLACES_DETAILS_URL = "https://places.googleapis.com/v1/places/";
const DEBOUNCE_MS = 300;
const MIN_CHARS = 3;

type GoogleAddressComponent = {
  longText?: string;
  shortText?: string;
  types?: string[];
};

function parseAddressComponents(
  components: GoogleAddressComponent[]
): AddressComponents {
  let streetNumber = "";
  let route = "";
  let city = "";
  let state = "";
  let zip = "";

  for (const c of components) {
    const types = c.types ?? [];
    if (types.includes("street_number")) streetNumber = c.longText ?? "";
    else if (types.includes("route")) route = c.longText ?? "";
    else if (types.includes("locality")) city = c.longText ?? "";
    else if (!city && types.includes("postal_town")) city = c.longText ?? "";
    else if (!city && types.includes("sublocality_level_1"))
      city = c.longText ?? "";
    else if (types.includes("administrative_area_level_1"))
      state = c.shortText ?? "";
    else if (types.includes("postal_code")) zip = c.longText ?? "";
  }

  const street = [streetNumber, route].filter(Boolean).join(" ");
  return { street, city, state, zip };
}

export function useAddressAutocomplete() {
  const [suggestions, setSuggestions] = useState<PlaceSuggestion[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const detailsAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      abortRef.current?.abort();
      detailsAbortRef.current?.abort();
    };
  }, []);

  const apiKey = import.meta.env.VITE_GOOGLE_PLACES_API_KEY;

  const fetchSuggestions = useCallback(
    async (input: string) => {
      if (!apiKey || input.length < MIN_CHARS) {
        setSuggestions([]);
        setIsOpen(false);
        return;
      }

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const resp = await fetch(PLACES_AUTOCOMPLETE_URL, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": apiKey,
          },
          body: JSON.stringify({
            input,
            includedRegionCodes: ["us"],
            includedPrimaryTypes: ["street_address", "subpremise"],
          }),
          signal: controller.signal,
        });

        if (!resp.ok) {
          setSuggestions([]);
          setIsOpen(false);
          return;
        }

        const data = await resp.json();
        const results: PlaceSuggestion[] = (data.suggestions ?? [])
          .filter((s: Record<string, unknown>) => {
            const pred = s.placePrediction as
              | { structuredFormat?: unknown; placeId?: unknown }
              | undefined;
            return (
              pred !== undefined &&
              pred.structuredFormat !== undefined &&
              typeof pred.placeId === "string"
            );
          })
          .map(
            (s: {
              placePrediction: {
                placeId: string;
                text: { text: string };
                structuredFormat: {
                  mainText: { text: string };
                  secondaryText: { text: string };
                };
              };
            }) => ({
              mainText: s.placePrediction.structuredFormat.mainText.text,
              secondaryText:
                s.placePrediction.structuredFormat.secondaryText.text,
              fullText: s.placePrediction.text.text,
              placeId: s.placePrediction.placeId,
            })
          );

        setSuggestions(results);
        setIsOpen(results.length > 0);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setSuggestions([]);
        setIsOpen(false);
      }
    },
    [apiKey]
  );

  const fetchPlaceDetails = useCallback(
    async (placeId: string): Promise<AddressComponents | null> => {
      if (!apiKey) return null;
      detailsAbortRef.current?.abort();
      const controller = new AbortController();
      detailsAbortRef.current = controller;
      try {
        const resp = await fetch(`${PLACES_DETAILS_URL}${placeId}`, {
          method: "GET",
          headers: {
            "X-Goog-Api-Key": apiKey,
            "X-Goog-FieldMask": "addressComponents",
          },
          signal: controller.signal,
        });
        if (!resp.ok) return null;
        const data = (await resp.json()) as {
          addressComponents?: GoogleAddressComponent[];
        };
        if (!data.addressComponents) return null;
        return parseAddressComponents(data.addressComponents);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return null;
        return null;
      }
    },
    [apiKey]
  );

  const onInputChange = useCallback(
    (value: string) => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (!value || value.length < MIN_CHARS) {
        setSuggestions([]);
        setIsOpen(false);
        return;
      }
      timerRef.current = setTimeout(() => fetchSuggestions(value), DEBOUNCE_MS);
    },
    [fetchSuggestions]
  );

  const close = useCallback(() => {
    setIsOpen(false);
  }, []);

  const clear = useCallback(() => {
    setSuggestions([]);
    setIsOpen(false);
    abortRef.current?.abort();
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  return {
    suggestions,
    isOpen,
    onInputChange,
    fetchPlaceDetails,
    close,
    clear,
  };
}
```

- [ ] **Step 2: Type-check**

Run from `frontend/`:
```bash
npx tsc --noEmit && npm run lint
```
Expected: success.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useAddressAutocomplete.ts
git commit -m "feat(address): surface placeId and add fetchPlaceDetails to autocomplete hook"
```

---

## Task 9: Rewrite `AddressSearch.tsx` as a four-field form

**Files:**
- Modify: `frontend/src/components/AddressSearch.tsx`

- [ ] **Step 1: Replace the file with the structured form**

Open `frontend/src/components/AddressSearch.tsx` and replace the entire file contents with:

```tsx
import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAddressAutocomplete } from "@/hooks/useAddressAutocomplete";
import { US_STATES } from "@/lib/usStates";

interface AddressSearchProps {
  onSearch: (address: string) => void;
  loading: boolean;
}

const ZIP_REGEX = /^\d{5}(-\d{4})?$/;

export function AddressSearch({ onSearch, loading }: AddressSearchProps) {
  const [street, setStreet] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [zip, setZip] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const { suggestions, isOpen, onInputChange, fetchPlaceDetails, close, clear } =
    useAddressAutocomplete();
  const streetWrapperRef = useRef<HTMLDivElement>(null);

  const isValid =
    street.trim().length > 0 &&
    city.trim().length > 0 &&
    state.length > 0 &&
    ZIP_REGEX.test(zip.trim());

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        streetWrapperRef.current &&
        !streetWrapperRef.current.contains(e.target as Node)
      ) {
        close();
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [close]);

  async function selectSuggestion(placeId: string, fallbackFullText: string) {
    clear();
    setHighlightedIndex(-1);
    const details = await fetchPlaceDetails(placeId);
    if (details) {
      if (details.street) setStreet(details.street);
      else setStreet(fallbackFullText);
      if (details.city) setCity(details.city);
      if (details.state) setState(details.state);
      if (details.zip) setZip(details.zip);
    } else {
      // Place Details failed — leave the user with the picked text in Street.
      setStreet(fallbackFullText);
    }
  }

  function handleStreetChange(value: string) {
    setStreet(value);
    setHighlightedIndex(-1);
    onInputChange(value);
  }

  function handleStreetKeyDown(e: React.KeyboardEvent) {
    if (!isOpen || suggestions.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIndex((i) => (i < suggestions.length - 1 ? i + 1 : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((i) => (i > 0 ? i - 1 : suggestions.length - 1));
    } else if (e.key === "Enter" && highlightedIndex >= 0) {
      e.preventDefault();
      const picked = suggestions[highlightedIndex];
      void selectSuggestion(picked.placeId, picked.fullText);
    } else if (e.key === "Escape") {
      close();
      setHighlightedIndex(-1);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValid) return;
    clear();
    onSearch(`${street.trim()}, ${city.trim()}, ${state} ${zip.trim()}`);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-4 w-full max-w-xl"
    >
      {/* Street with autocomplete */}
      <div className="flex flex-col gap-1">
        <label htmlFor="street" className="text-sm font-medium">
          Street address
        </label>
        <div ref={streetWrapperRef} className="relative">
          <Input
            id="street"
            type="text"
            placeholder="123 Main St"
            value={street}
            onChange={(e) => handleStreetChange(e.target.value)}
            onKeyDown={handleStreetKeyDown}
            disabled={loading}
            autoComplete="off"
            role="combobox"
            aria-expanded={isOpen}
            aria-autocomplete="list"
            aria-controls="address-suggestions"
            aria-activedescendant={
              highlightedIndex >= 0 ? `suggestion-${highlightedIndex}` : undefined
            }
          />
          {isOpen && suggestions.length > 0 && (
            <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-md">
              <ul id="address-suggestions" role="listbox">
                {suggestions.map((s, i) => (
                  <li
                    key={`${s.placeId}-${i}`}
                    id={`suggestion-${i}`}
                    role="option"
                    aria-selected={i === highlightedIndex}
                    className={`cursor-pointer px-3 py-2 text-sm ${
                      i === highlightedIndex
                        ? "bg-primary text-primary-foreground"
                        : "hover:bg-accent/50"
                    }`}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      void selectSuggestion(s.placeId, s.fullText);
                    }}
                    onMouseEnter={() => setHighlightedIndex(i)}
                  >
                    <span className="font-medium">{s.mainText}</span>{" "}
                    <span
                      className={`text-xs ${
                        i === highlightedIndex
                          ? "opacity-80"
                          : "text-muted-foreground"
                      }`}
                    >
                      {s.secondaryText}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="px-3 py-1.5 text-[10px] text-muted-foreground text-right border-t">
                Powered by Google
              </div>
            </div>
          )}
        </div>
      </div>

      {/* City | State | ZIP */}
      <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto_auto] gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="city" className="text-sm font-medium">
            City
          </label>
          <Input
            id="city"
            type="text"
            placeholder="Austin"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            disabled={loading}
            autoComplete="off"
          />
        </div>
        <div className="flex flex-col gap-1 sm:w-40">
          <label htmlFor="state" className="text-sm font-medium">
            State
          </label>
          <Select value={state} onValueChange={setState} disabled={loading}>
            <SelectTrigger id="state">
              <SelectValue placeholder="Select" />
            </SelectTrigger>
            <SelectContent>
              {US_STATES.map((s) => (
                <SelectItem key={s.code} value={s.code}>
                  {s.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1 sm:w-32">
          <label htmlFor="zip" className="text-sm font-medium">
            ZIP code
          </label>
          <Input
            id="zip"
            type="text"
            inputMode="numeric"
            maxLength={10}
            placeholder="78701"
            value={zip}
            onChange={(e) => setZip(e.target.value)}
            disabled={loading}
            autoComplete="off"
          />
        </div>
      </div>

      <div>
        <Button type="submit" disabled={loading || !isValid}>
          {loading ? "Searching…" : "Search"}
        </Button>
      </div>
    </form>
  );
}
```

- [ ] **Step 2: Type-check and lint**

Run from `frontend/`:
```bash
npx tsc --noEmit && npm run lint && npm run build
```
Expected: all three succeed.

- [ ] **Step 3: Manual verification — happy path**

Run from `frontend/`:
```bash
npm run dev
```
Open http://localhost:5173. With a real `VITE_GOOGLE_PLACES_API_KEY` set:

1. Click the Street field, start typing `1600 Penns…` — suggestions appear in a dropdown below the Street field.
2. Pick `1600 Pennsylvania Ave NW, Washington, DC, USA`.
3. Verify Street, City, State, ZIP all populate (`1600 Pennsylvania Avenue NW`, `Washington`, `DC`, `20500`).
4. Click Search — page navigates to `/reps`, results load.

- [ ] **Step 4: Manual verification — edge cases**

5. Refresh, type a partial address, then manually edit each field after picking. Submit — verify submit string contains the edits (check the network request to `/api/representatives` in DevTools).
6. Refresh, type `1600 Pennsylvania Ave NW`, do NOT pick a suggestion — fill City/State/ZIP manually. Submit — should still work.
7. Refresh, type a real address but enter ZIP `123` — Search button is disabled. Change ZIP to `78701` — button enables.
8. Refresh, leave State empty — Search disabled.
9. Press Escape while suggestions are open — dropdown closes; fields still populated.

Stop the dev server.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/AddressSearch.tsx
git commit -m "feat(address): rewrite AddressSearch as structured 4-field form"
```

---

## Task 10: Final integration check + push

**Files:** none modified

- [ ] **Step 1: Full build + lint + typecheck**

Run from `frontend/`:
```bash
npx tsc --noEmit && npm run lint && npm run build
```
Expected: all three succeed.

- [ ] **Step 2: End-to-end manual smoke test**

Run from `frontend/`:
```bash
npm run dev
```

Walk through:
1. Landing page: serif "KnowMyReps" h1, ivory background, navy text, navy-star favicon in tab.
2. Address form: type, pick, all four fields fill, Search enabled.
3. `/reps`: serif group labels ("Federal", etc.), serif rep names on cards, party badges in soft navy / soft oxblood / warm gray.
4. Click "Generate AI Overview" on any rep — overview renders with Inter body type.
5. `/elections`: candidate cards reuse RepCard styling — same theme.
6. `/issues`: enter an issue, run multi-rep — `IssueCompareResult` rows render party badges with new colors.
7. Toggle dark mode by adding `dark` class to `<html>` in DevTools — verify ink-blue background, parchment text, oxblood accent. Remove the class.

Stop the dev server.

- [ ] **Step 3: Push the branch**

```bash
git push -u origin address-form-federalist-theme
```

(Do not open a PR yet — leave that to the user.)

---

## Self-review notes

Cross-checked the plan against the spec on 2026-05-08:

- Spec §1 (address form) → Tasks 6, 7, 8, 9 (states list, select component, hook extension, form rewrite). Backend left unchanged (Task 9 Step 1 builds the concatenated string client-side).
- Spec §2 (palette + favicon) → Tasks 1, 3.
- Spec §3 (typography) → Tasks 2, 5.
- Spec §4 (party badges + cross-cutting) → Task 4.
- Verification block in spec → Task 9 Steps 3–4 (form), Task 10 Step 2 (theme).
- Commit shape suggested in spec ("theme + fonts + favicon + party badges first, then form") → Tasks 1–7 cover the theme half, Tasks 8–9 cover the form half. Order preserved.

Type consistency: `AddressComponents` (Task 8) used identically in Task 9. `PartyBadge` (Task 4) consumed by all three card components. `US_STATES` (Task 6) consumed by Task 9. No drift.

Placeholder scan: no TBD/TODO/"appropriate"/"as needed" — all code is concrete. The one conditional in Task 5 Step 3 (about `CardTitle` rendering) is a verification-and-branch, not a placeholder; both branches are spelled out.
