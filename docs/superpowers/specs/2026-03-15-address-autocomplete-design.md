# Address Autocomplete Design

## Problem

Users who don't enter their address exactly right get poor results. A standard address autocomplete dropdown (like Google Places) would guide users to valid, well-formatted addresses.

## Solution

Add Google Places Autocomplete to the `AddressSearch` component.

## API

**Endpoint:** `POST https://places.googleapis.com/v1/places:autocomplete`

**Required headers:**
- `Content-Type: application/json`
- `X-Goog-Api-Key: <key>`

**Request body:**
```json
{
  "input": "139 Frost",
  "includedRegionCodes": ["us"],
  "includedPrimaryTypes": ["street_address", "subpremise", "route", "locality"]
}
```

**Response shape (relevant fields):**
```json
{
  "suggestions": [
    {
      "placePrediction": {
        "text": { "text": "139 Frost Street, Brooklyn, NY, USA" },
        "structuredFormat": {
          "mainText": { "text": "139 Frost Street" },
          "secondaryText": { "text": "Brooklyn, NY, USA" }
        }
      }
    }
  ]
}
```

The new Places API supports browser CORS, unlike the legacy API.

## API Key

`GOOGLE_PLACES_API_KEY` — a new frontend-exposed env var. This can be the same GCP key as `GOOGLE_CIVIC_API_KEY` if the Places API (New) is enabled on it, or a separate key.

**Security:** Since `VITE_`-prefixed vars are embedded in the JS bundle, the key must be restricted in the Google Cloud Console:
- HTTP referrer restrictions (restrict to the app's domain)
- API restrictions (only allow Places API)

**Setup step:** The Places API (New) must be enabled in the Google Cloud Console for the GCP project.

## Frontend Changes

**`AddressSearch.tsx`** — replace the plain `<Input>` with an autocomplete input:

- Query Google Places Autocomplete as the user types (debounced ~300ms)
- Show a dropdown of address suggestions below the input
- When the user selects a suggestion, populate the input with the full formatted address and auto-submit the search (no extra "Search" click needed)
- Keyboard navigation: arrow keys to move, Enter to select, Escape to dismiss
- Click-outside dismisses the dropdown
- Minimum 3 characters before querying
- Users can still type a full address manually and click "Search" — autocomplete enhances but doesn't replace manual entry

**Graceful degradation:** If the API key is missing, the Places API errors, or the network is unavailable, the input falls back to plain text entry (current behavior). No error shown to the user — autocomplete simply doesn't appear.

**Integration approach:** Direct `fetch` to the Places API (New) REST endpoint. No `google.maps` script tag or heavy SDK — keeps the bundle lean.

## No Backend Changes

Autocomplete is purely a frontend concern. The backend continues to receive a full address string via `POST /api/representatives`.

## Styling

- Dropdown styled with Tailwind to match the existing shadcn/ui design system
- Each suggestion shows the main text (e.g., "139 Frost Street") with secondary text (e.g., "Brooklyn, NY, USA") in a smaller/muted style
- "Powered by Google" attribution displayed below the dropdown per Google's Terms of Service
