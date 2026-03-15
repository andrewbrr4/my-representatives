# Address Autocomplete Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Google Places Autocomplete to the address input so users get guided to valid addresses as they type.

**Architecture:** A custom `useAddressAutocomplete` hook handles debounced calls to the Google Places Autocomplete (New) REST API. The existing `AddressSearch` component gets a suggestion dropdown below the input. No backend changes. Graceful fallback to plain text if the API key is missing or the API errors.

**Tech Stack:** React 19, TypeScript, Vite (env vars), Tailwind v4, shadcn/ui `Input` component, Google Places API (New) REST endpoint.

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `frontend/src/hooks/useAddressAutocomplete.ts` | Debounced fetch to Places API, state management for suggestions |
| Modify | `frontend/src/components/AddressSearch.tsx` | Integrate autocomplete dropdown, keyboard nav, click-outside |
| Modify | `frontend/Dockerfile` | Add `VITE_GOOGLE_PLACES_API_KEY` build arg |
| Modify | `docker-compose.yml` | Pass env var to frontend service |
| Modify | `CLAUDE.md` | Document new env var |

---

## Chunk 1: Autocomplete Hook and UI

### Task 1: Create `useAddressAutocomplete` hook

**Files:**
- Create: `frontend/src/hooks/useAddressAutocomplete.ts`

- [ ] **Step 1: Create the hook file**

```ts
import { useState, useRef, useCallback } from "react";

interface PlaceSuggestion {
  mainText: string;
  secondaryText: string;
  fullText: string;
}

const PLACES_API_URL = "https://places.googleapis.com/v1/places:autocomplete";
const DEBOUNCE_MS = 300;
const MIN_CHARS = 3;

export function useAddressAutocomplete() {
  const [suggestions, setSuggestions] = useState<PlaceSuggestion[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Build-time constant — listed in dependency array for correctness
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
        const resp = await fetch(PLACES_API_URL, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": apiKey,
          },
          body: JSON.stringify({
            input,
            includedRegionCodes: ["us"],
            includedPrimaryTypes: [
              "street_address",
              "subpremise",
              "route",
              "locality",
            ],
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
          .filter(
            (s: Record<string, unknown>) => s.placePrediction !== undefined
          )
          .map(
            (s: {
              placePrediction: {
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
            })
          );

        setSuggestions(results);
        setIsOpen(results.length > 0);
      } catch (err) {
        // Aborted requests (from new keystrokes) should not clear state
        if (err instanceof DOMException && err.name === "AbortError") return;
        setSuggestions([]);
        setIsOpen(false);
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

  return { suggestions, isOpen, onInputChange, close, clear };
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd /Users/andrewbarry/projects/my-representatives/frontend && npx tsc --noEmit`
Expected: No errors related to the new file.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useAddressAutocomplete.ts
git commit -m "feat: add useAddressAutocomplete hook for Google Places API"
```

---

### Task 2: Integrate autocomplete into `AddressSearch`

**Files:**
- Modify: `frontend/src/components/AddressSearch.tsx`

- [ ] **Step 1: Rewrite AddressSearch with autocomplete dropdown**

Replace the contents of `AddressSearch.tsx` with:

```tsx
import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAddressAutocomplete } from "@/hooks/useAddressAutocomplete";

interface AddressSearchProps {
  onSearch: (address: string) => void;
  loading: boolean;
}

export function AddressSearch({ onSearch, loading }: AddressSearchProps) {
  const [address, setAddress] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const { suggestions, isOpen, onInputChange, close, clear } =
    useAddressAutocomplete();
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Click-outside to dismiss dropdown
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(e.target as Node)
      ) {
        close();
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [close]);

  // Selecting a suggestion populates the input and auto-submits the search
  function selectSuggestion(fullText: string) {
    setAddress(fullText);
    clear();
    setHighlightedIndex(-1);
    onSearch(fullText);
  }

  function handleInputChange(value: string) {
    setAddress(value);
    setHighlightedIndex(-1);
    onInputChange(value);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (!isOpen || suggestions.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIndex((i) =>
        i < suggestions.length - 1 ? i + 1 : 0
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIndex((i) =>
        i > 0 ? i - 1 : suggestions.length - 1
      );
    } else if (e.key === "Enter" && highlightedIndex >= 0) {
      e.preventDefault();
      selectSuggestion(suggestions[highlightedIndex].fullText);
    } else if (e.key === "Escape") {
      close();
      setHighlightedIndex(-1);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (address.trim()) {
      clear();
      onSearch(address.trim());
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-3 w-full max-w-xl">
      <div ref={wrapperRef} className="relative flex-1">
        <Input
          type="text"
          placeholder="Enter your address (e.g. 123 Main St, Austin, TX 78701)"
          value={address}
          onChange={(e) => handleInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          className="w-full"
          disabled={loading}
          autoComplete="off"
          role="combobox"
          aria-expanded={isOpen}
          aria-autocomplete="list"
          aria-controls="address-suggestions"
          aria-activedescendant={
            highlightedIndex >= 0
              ? `suggestion-${highlightedIndex}`
              : undefined
          }
        />
        {isOpen && suggestions.length > 0 && (
          <ul
            id="address-suggestions"
            role="listbox"
            className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-md"
          >
            {suggestions.map((s, i) => (
              <li
                key={`${s.fullText}-${i}`}
                id={`suggestion-${i}`}
                role="option"
                aria-selected={i === highlightedIndex}
                className={`cursor-pointer px-3 py-2 text-sm ${
                  i === highlightedIndex
                    ? "bg-accent text-accent-foreground"
                    : "hover:bg-accent/50"
                }`}
                onMouseDown={(e) => {
                  e.preventDefault();
                  selectSuggestion(s.fullText);
                }}
                onMouseEnter={() => setHighlightedIndex(i)}
              >
                <span className="font-medium">{s.mainText}</span>{" "}
                <span className="text-muted-foreground text-xs">
                  {s.secondaryText}
                </span>
              </li>
            ))}
            <li className="px-3 py-1.5 text-[10px] text-muted-foreground text-right">
              Powered by Google
            </li>
          </ul>
        )}
      </div>
      <Button type="submit" disabled={loading || !address.trim()}>
        {loading ? "Searching…" : "Search"}
      </Button>
    </form>
  );
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd /Users/andrewbarry/projects/my-representatives/frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 3: Manual smoke test**

Run: `cd /Users/andrewbarry/projects/my-representatives/frontend && npm run dev`

Test:
1. Type "123 Main" — dropdown should appear with suggestions (requires `VITE_GOOGLE_PLACES_API_KEY` in `frontend/.env`)
2. Arrow keys navigate the list, Enter selects and auto-submits
3. Escape dismisses dropdown
4. Clicking a suggestion selects and auto-submits
5. Clicking outside dismisses dropdown
6. Typing a full address and clicking "Search" still works (manual fallback)
7. If `VITE_GOOGLE_PLACES_API_KEY` is not set, input works exactly like before (no dropdown, no errors)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/AddressSearch.tsx
git commit -m "feat: integrate address autocomplete dropdown into AddressSearch"
```

---

### Task 3: Update Dockerfile, docker-compose, and docs

**Files:**
- Modify: `frontend/Dockerfile:11-12` — add build arg (insert after line 12, before `RUN npm run build` on line 14)
- Modify: `docker-compose.yml:12-22` — add `env_file` to frontend service
- Modify: `CLAUDE.md` — document new env var

- [ ] **Step 1: Add build arg to Dockerfile**

In `frontend/Dockerfile`, insert these two lines immediately after line 12 (`ENV VITE_API_URL=$VITE_API_URL`) and before line 14 (`RUN npm run build`):

```dockerfile
ARG VITE_GOOGLE_PLACES_API_KEY
ENV VITE_GOOGLE_PLACES_API_KEY=$VITE_GOOGLE_PLACES_API_KEY
```

- [ ] **Step 2: Add env_file to frontend service in docker-compose.yml**

In `docker-compose.yml`, add `env_file` to the `frontend` service so the Vite dev server has access to `VITE_GOOGLE_PLACES_API_KEY`. Insert after line 16 (`dockerfile: Dockerfile.dev`):

```yaml
    env_file:
      - .env
```

- [ ] **Step 3: Add env var to CLAUDE.md**

In the "Environment Variables" section of `CLAUDE.md`, insert after the `GOOGLE_CIVIC_API_KEY` line:

```
- `VITE_GOOGLE_PLACES_API_KEY` — Google Places API key for address autocomplete (frontend env var, read by Vite; must have Places API (New) enabled in GCP console; restrict by HTTP referrer for security)
```

**Note on env file location:** For local dev (`cd frontend && npm run dev`), Vite reads `.env` from the working directory, so the key should go in `frontend/.env`. For Docker Compose, the `env_file: .env` directive reads from the project root `.env`. If using a single root `.env`, create a `frontend/.env` that references or duplicates the key.

- [ ] **Step 4: Final build check**

Run: `cd /Users/andrewbarry/projects/my-representatives/frontend && npm run build`
Expected: Build succeeds with no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/Dockerfile docker-compose.yml CLAUDE.md
git commit -m "chore: add VITE_GOOGLE_PLACES_API_KEY to Dockerfile, docker-compose, and docs"
```
