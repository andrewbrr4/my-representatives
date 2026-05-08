# Structured Address Form + Federalist Patriotic Theme — Design

**Status:** Approved (single-PR delivery)
**Author:** Andrew (with Claude)
**Date:** 2026-05-08

## Goal

Two changes shipped together in one PR:

1. **Structured address form.** Replace the single-field address autocomplete with a four-field form (Street, City, State dropdown, ZIP). Street keeps Google Places autocomplete; selecting a suggestion fills the other three.
2. **Federalist patriotic visual refresh.** Swap the monochrome shadcn-default theme for a civic/Federalist palette (ivory, deep navy, oxblood). Editorial typography (Source Serif 4 headings, Inter body). Recolor party badges to the new palette. Replace the default Vite favicon with a navy 5-point star.

Both are frontend-only; the backend contract is unchanged.

## Section 1 — Structured address form

### User flow

1. User lands on `/` (SearchPage).
2. Sees four fields stacked: **Street address** (full-width), then a row of **City** | **State** (dropdown) | **ZIP**.
3. Types into **Street**. After the existing 300ms debounce + 3-char minimum, the Google Places dropdown appears (same UI as today: navy highlight on the active suggestion, "Powered by Google" footer).
4. User picks a suggestion (click or Enter while highlighted).
5. The frontend fires a Place Details call for the chosen `placeId`, parses `addressComponents`, and populates **Street**, **City**, **State**, **ZIP**. The autocomplete dropdown closes.
6. All four fields remain editable — user can correct any field.
7. **Search** button is enabled only when all four fields pass validation. Click → frontend concatenates `${street}, ${city}, ${state} ${zip}` into a single string and dispatches `setAddress(...)` (which the existing `AddressContext` already navigates on).

### Hook contract — `useAddressAutocomplete`

The hook currently returns `{ suggestions, isOpen, onInputChange, close, clear }` where each suggestion is `{ mainText, secondaryText, fullText }`.

**Changes:**

- Add `placeId: string` to each suggestion (it is already in the response payload at `s.placePrediction.placeId` — the hook just needs to surface it).
- Add a new exported function `fetchPlaceDetails(placeId: string): Promise<AddressComponents | null>` to the same hook. It calls:
  ```
  POST https://places.googleapis.com/v1/places/{placeId}
  Headers:
    X-Goog-Api-Key: <VITE_GOOGLE_PLACES_API_KEY>
    X-Goog-FieldMask: addressComponents
  ```
  and parses the response into:
  ```ts
  type AddressComponents = {
    street: string;   // street_number + " " + route
    city: string;     // locality (fallback: postal_town, sublocality_level_1)
    state: string;    // administrative_area_level_1.shortText (e.g. "TX")
    zip: string;      // postal_code
  };
  ```
- On any field that cannot be derived (e.g. PO box with no `route`), the function returns the partial value the user can correct manually. If the request fails, it returns `null` and the form stays as the user typed.
- The hook owns its own `AbortController` for Place Details (separate from the autocomplete controller) so a stale details fetch can't overwrite a newer pick.

### New file — `src/lib/usStates.ts`

Static export, no runtime dependencies:

```ts
export const US_STATES: ReadonlyArray<{ code: string; name: string }> = [
  { code: "AL", name: "Alabama" },
  // …51 entries: 50 states + DC, alphabetical by name
];
```

Used by the State dropdown's `<option>` list.

### Component — `AddressSearch.tsx` rewrite

- Replace internal state `address`/`selectedFullText` with four pieces of state: `street`, `city`, `state`, `zip`.
- Replace the single `<Input>` with a `<form>` that contains:
  - Street: `<Input>` wrapped in the existing autocomplete dropdown wrapper. Label "Street address" above. `placeholder="123 Main St"`.
  - City: `<Input>`. Label "City". `placeholder="Austin"`.
  - State: shadcn `<Select>` (newly added). Label "State". Options from `US_STATES`. Default empty/`Select…`.
  - ZIP: `<Input inputMode="numeric" maxLength={10}>`. Label "ZIP code". Validation regex `/^\d{5}(-\d{4})?$/`.
- Submit button copy unchanged: `Searching…` / `Search`.
- Layout: stacked Street and (City | State | ZIP) row. Mobile: each on its own row. Tailwind classes; no new layout primitives.
- On suggestion select: call `fetchPlaceDetails`, then `setStreet`, `setCity`, `setState`, `setZip` from the result (only overwriting the field if the parsed value is non-empty so partial responses don't blank out a field the user already typed). Clear suggestions and close dropdown.
- On submit: `onSearch(`${street.trim()}, ${city.trim()}, ${state} ${zip.trim()}`)`.
- Form is invalid (Search disabled) until: Street non-empty, City non-empty, State chosen, ZIP matches regex.

### Backend

**No changes.** The single concatenated string flows into `/api/representatives` and `/api/elections` exactly as today. Census Geocoder and Cicero already accept `"123 Main St, Austin, TX 78701"`.

### New shadcn component

Run `cd frontend && npx shadcn@latest add select`. This generates `src/components/ui/select.tsx` (Radix-based). No manual edits expected.

### Edge cases

- **Place Details fails / network error.** `fetchPlaceDetails` returns `null`; we leave the form empty and let the user fill it manually. No error toast — the user can still type.
- **Partial components from Google.** Some addresses (rural, PO box) won't include all four. We populate what we get; the user fills the rest.
- **User edits a field after selecting a suggestion.** Edits stay; we don't re-fire Place Details. The submit string is built from current field state.
- **State dropdown receives a code Google didn't return** (e.g. user picked a Mexico address by mistake). Validation requires a chosen state; if Google gave us nothing, dropdown stays at the empty default and Search remains disabled.

---

## Section 2 — Federalist palette + favicon

### Palette tokens

Replace `:root` and `.dark` blocks in `src/index.css`. Values are oklch, chosen for AA contrast on the body background and a cohesive low-saturation feel.

**Light (`:root`):**

| Token | New value | Role |
|---|---|---|
| `--background` | `oklch(0.97 0.012 85)` | Ivory page background |
| `--foreground` | `oklch(0.22 0.06 255)` | Deep navy body text |
| `--card` | `oklch(0.99 0.008 85)` | Slightly brighter ivory for cards |
| `--card-foreground` | `oklch(0.22 0.06 255)` | Same as foreground |
| `--popover` | `oklch(0.99 0.008 85)` | Same as card |
| `--popover-foreground` | `oklch(0.22 0.06 255)` | |
| `--primary` | `oklch(0.30 0.10 255)` | Navy — used for buttons, active tab underline |
| `--primary-foreground` | `oklch(0.97 0.012 85)` | Ivory on navy |
| `--secondary` | `oklch(0.93 0.014 85)` | Soft warm gray |
| `--secondary-foreground` | `oklch(0.30 0.10 255)` | Navy |
| `--muted` | `oklch(0.93 0.014 85)` | Same as secondary |
| `--muted-foreground` | `oklch(0.48 0.04 255)` | Mid-tone navy-gray |
| `--accent` | `oklch(0.40 0.15 25)` | Oxblood (used for emphasis: link hover, accent strokes) |
| `--accent-foreground` | `oklch(0.97 0.012 85)` | Ivory on oxblood |
| `--destructive` | (unchanged — bright red is functionally distinct from oxblood) |
| `--border` | `oklch(0.86 0.014 85)` | Warm gray border |
| `--input` | `oklch(0.86 0.014 85)` | Same as border |
| `--ring` | `oklch(0.30 0.10 255)` | Navy focus ring |

**Dark (`.dark`):**

| Token | New value |
|---|---|
| `--background` | `oklch(0.18 0.05 255)` (ink-blue) |
| `--foreground` | `oklch(0.94 0.012 85)` (parchment) |
| `--card` | `oklch(0.23 0.06 255)` |
| `--primary` | `oklch(0.85 0.06 85)` (warm parchment used as primary on dark) |
| `--primary-foreground` | `oklch(0.18 0.05 255)` |
| `--accent` | `oklch(0.55 0.18 25)` (oxblood, brighter for dark) |
| (others scale proportionally) |

The `chart-*` and `sidebar-*` tokens are unused on this site (no charts, no sidebar) but get refreshed values to stay self-consistent if future surfaces use them.

**Validation:** spot-check `--foreground` on `--background` for AA (≥4.5:1) — the navy/ivory pair does. Verify `--accent-foreground` on `--accent` (ivory on oxblood) AA. Verify `--muted-foreground` on `--background` AA for body de-emphasized text.

### Favicon

- **New file:** `frontend/public/star.svg`. Single 5-point star, navy fill (`#0E2D4F`), no background (transparent), centered in a 32×32 viewBox.
  ```svg
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
    <path d="M16 2 L19.6 12.4 L30.5 12.4 L21.6 19 L25.2 29.4 L16 22.8 L6.8 29.4 L10.4 19 L1.5 12.4 L12.4 12.4 Z" fill="#0E2D4F"/>
  </svg>
  ```
- **Update:** `frontend/index.html` line `<link rel="icon" type="image/svg+xml" href="/vite.svg" />` → `href="/star.svg"`.
- **Delete:** `frontend/public/vite.svg`.

---

## Section 3 — Typography

### Fonts

Self-host both faces via `@fontsource` so there's no external network call, no CLS, and no GDPR concern.

```bash
npm install @fontsource/source-serif-4 @fontsource/inter
```

In `src/main.tsx` (top of file, before any component imports):

```ts
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/source-serif-4/600.css";
import "@fontsource/source-serif-4/700.css";
```

This loads only the weights actually used (~50 KB total post-compression).

### Type scale and font assignment in `index.css`

Add to the `@layer base` block:

```css
@layer base {
  body {
    font-family: "Inter", ui-sans-serif, system-ui, sans-serif;
  }
  h1, h2, h3, .font-display {
    font-family: "Source Serif 4", ui-serif, Georgia, serif;
  }
}
```

Class usage stays Tailwind-native — `text-4xl font-bold` on an `<h1>` automatically renders in serif because of the element selector. No bespoke utility classes needed for the common case. The `.font-display` escape hatch is for the rare `<div>` or `<span>` that needs to render in serif.

### Per-page heading sizing (no markup-shape changes)

| Surface | Today | New |
|---|---|---|
| `SearchPage.tsx` h1 "KnowMyReps" | `text-4xl font-bold tracking-tight` | `text-5xl font-bold tracking-tight` (serif inherits) |
| `RepresentativesPage.tsx` group label h2 ("Federal" / "State" / "Municipal") | `text-xl font-semibold` | `text-2xl font-semibold` (serif inherits) |
| `RepCard.tsx` `<CardTitle>` rep name | `text-lg` | `text-xl font-semibold` (serif inherits via CardTitle being an h3) |
| `CandidateCard.tsx` `<CardTitle>` | `text-lg` | `text-xl font-semibold` (serif inherits) |
| Body copy / `<CardDescription>` / muted meta | unchanged sizes, Inter inherits via body |

**Verify:** the shadcn `Card` component renders `CardTitle` as a styled `<div>` with text styling, not an `<h3>`. If so, add an explicit `as="h3"` or wrap the prop in a heading element so the serif rule applies. (Spec assumes the latter; the implementation step verifies the actual rendered tag and adjusts.)

---

## Section 4 — Party badges + cross-cutting touches

### New shared util — `src/lib/partyBadge.ts`

Three components currently inline an identical `getPartyBadge` function: `RepCard.tsx`, `CandidateCard.tsx`, `IssueCompareResult.tsx`. Extract to one shared util as part of this work (the badges all change colors anyway — collapsing the duplication first means we recolor in one place).

**Tokenize the party colors** so the util uses the same theme system as the rest of the chrome (and we can retune them in `index.css` without touching React code). Add three tokens to `:root` and `.dark` in `index.css`:

```css
:root {
  --party-democrat: oklch(0.30 0.10 255);
  --party-republican: oklch(0.40 0.15 25);
  --party-independent: oklch(0.55 0.02 85);
}
.dark {
  --party-democrat: oklch(0.55 0.10 255);
  --party-republican: oklch(0.55 0.18 25);
  --party-independent: oklch(0.62 0.02 85);
}
```

Map them in the existing `@theme inline` block:

```css
--color-party-democrat: var(--party-democrat);
--color-party-republican: var(--party-republican);
--color-party-independent: var(--party-independent);
```

That makes `bg-party-democrat`, `bg-party-republican`, `bg-party-independent` first-class Tailwind utilities. The shared util uses them:

```ts
export type PartyBadge = { label: string; className: string };

export function getPartyBadge(party: string | null): PartyBadge | null {
  if (!party) return null;
  const p = party.trim().toLowerCase();
  if (p === "d" || p.startsWith("democrat")) {
    const label = p.startsWith("democratic") ? "Democratic" : "Democrat";
    return { label, className: "bg-party-democrat text-primary-foreground hover:bg-party-democrat/90" };
  }
  if (p === "r" || p.startsWith("republican")) {
    return { label: "Republican", className: "bg-party-republican text-primary-foreground hover:bg-party-republican/90" };
  }
  if (p === "i" || p.startsWith("independent")) {
    return { label: "Independent", className: "bg-party-independent text-primary-foreground hover:bg-party-independent/90" };
  }
  return null;
}
```

### Touched components

| File | Change |
|---|---|
| `src/index.css` | New palette tokens (light + dark), 3 new `--party-*` tokens, `@theme inline` mapping, `@layer base` font-family rules |
| `src/main.tsx` | `@fontsource` imports |
| `index.html` | favicon href |
| `public/star.svg` | new file |
| `public/vite.svg` | delete |
| `src/lib/partyBadge.ts` | new — shared util |
| `src/lib/usStates.ts` | new — state list |
| `src/components/ui/select.tsx` | new — generated by `npx shadcn add select` |
| `src/hooks/useAddressAutocomplete.ts` | surface `placeId`, add `fetchPlaceDetails` |
| `src/components/AddressSearch.tsx` | rewrite to four-field form |
| `src/components/RepCard.tsx` | import shared `getPartyBadge`, delete local copy |
| `src/components/CandidateCard.tsx` | same |
| `src/components/IssueCompareResult.tsx` | same |
| `src/pages/SearchPage.tsx` | bump h1 size if needed; otherwise inherits |
| `src/pages/RepresentativesPage.tsx` | bump group label sizing if needed; otherwise inherits |
| `package.json` / `package-lock.json` | `@fontsource/inter`, `@fontsource/source-serif-4` |

`TabNav.tsx` uses `border-primary` for the active underline and inherits the new navy automatically — no changes. `Button`, `Input`, `Badge`, `Card` all read theme tokens — no changes. `IssueSearch`, `ElectionCard`, `FurtherReading`, `CrossLinkCards` use only theme tokens for color — no changes (verify visually during impl).

---

## Out of scope

- **Server-side address normalization.** We continue to send a concatenated string. If geocoding accuracy becomes an issue, that's a follow-up.
- **Stylistic changes inside the AI Overview / research bullets.** The bullets render through `ResearchContent` — body type inherits the new Inter automatically. No prose-component restructuring this PR.
- **Mobile keyboard tuning beyond `inputMode="numeric"` for ZIP.** No address-autocomplete-specific keyboard config.
- **i18n / non-US addresses.** Out of scope; the app is US-only by design.
- **Logo wordmark.** Favicon only. The "KnowMyReps" wordmark on `SearchPage` stays plain serif text — no graphical lockup this PR.

## Verification

Manual UI verification for both halves of the PR:

1. **Address form** (theme + form):
   - Type a real address in Street, pick a suggestion → all four fields populate correctly.
   - Edit the populated City → still able to submit; submitted string contains the edit.
   - Clear the State dropdown → Search becomes disabled.
   - Type an invalid ZIP ("123") → Search disabled; switch to "78701" → enabled.
   - Submit → land on `/reps`, results load as today.

2. **Theme** (look right in both modes):
   - Light mode: ivory background, navy headings, oxblood accent on link hover. Party badges read as soft navy / soft oxblood / warm gray, not as bright as before.
   - Dark mode (`.dark` on `<html>`): ink-blue background, parchment text, headings still serif.
   - Favicon star visible in browser tab.
   - `npm run build` succeeds (typecheck + bundle).
   - `npm run lint` clean.
   - Spot-check focus ring visible on Search button (navy ring on ivory).

## Notes for the implementation plan

This is a single-PR delivery on a fresh branch off `main`. Suggested commit shape (one branch, multiple commits):

1. Theme tokens + fonts + favicon + party-badge util extraction (no behavior change beyond colors/typography).
2. `useAddressAutocomplete` extension (`placeId` + `fetchPlaceDetails`).
3. `AddressSearch` rewrite + `usStates` + shadcn `select`.
4. Cleanup commit if any per-page sizing tweaks land separately.

The implementation plan should sequence in that order so each commit is independently runnable and easy to bisect.
