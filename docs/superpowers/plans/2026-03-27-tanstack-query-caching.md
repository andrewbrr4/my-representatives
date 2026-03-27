# TanStack Query Client-Side Caching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace custom data-fetching hooks with TanStack Query so data persists across route changes and research polling is simplified.

**Architecture:** Add `@tanstack/react-query` as a dependency. Create a `QueryClientProvider` at the app root. Replace four custom hooks (`useRepresentatives`, `useElections`, `useResearch`, `useElectionResearch`) with TanStack Query equivalents that use global cache keys. Research triggering uses mutations; research polling uses queries with conditional `refetchInterval`.

**Tech Stack:** React 19, TanStack Query v5, TypeScript, Vite

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `frontend/package.json` | Modify | Add `@tanstack/react-query` dependency |
| `frontend/src/main.tsx` | Modify | Add `QueryClientProvider` |
| `frontend/src/lib/queryClient.ts` | Create | QueryClient singleton with default options |
| `frontend/src/hooks/useRepresentativesQuery.ts` | Create | TanStack Query hook for rep lookup |
| `frontend/src/hooks/useElectionsQuery.ts` | Create | TanStack Query hook for election lookup |
| `frontend/src/hooks/useResearchQuery.ts` | Create | TanStack Query mutation + polling for rep research |
| `frontend/src/hooks/useElectionResearchQuery.ts` | Create | TanStack Query polling for election research |
| `frontend/src/pages/RepresentativesPage.tsx` | Modify | Consume new hooks |
| `frontend/src/pages/ElectionsPage.tsx` | Modify | Consume new hooks |
| `frontend/src/hooks/useRepresentatives.ts` | Delete | Replaced |
| `frontend/src/hooks/useElections.ts` | Delete | Replaced |
| `frontend/src/hooks/useResearch.ts` | Delete | Replaced |
| `frontend/src/hooks/useElectionResearch.ts` | Delete | Replaced |

---

### Task 1: Install TanStack Query and Create QueryClient

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/lib/queryClient.ts`
- Modify: `frontend/src/main.tsx`

- [ ] **Step 1: Install dependency**

```bash
cd frontend && npm install @tanstack/react-query
```

- [ ] **Step 2: Create QueryClient singleton**

Create `frontend/src/lib/queryClient.ts`:

```typescript
import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});
```

- [ ] **Step 3: Add QueryClientProvider to main.tsx**

Modify `frontend/src/main.tsx` to wrap the app:

```typescript
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/lib/queryClient";
import { AddressProvider } from "@/contexts/AddressContext";
import "./index.css";
import App from "./App.tsx";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <AddressProvider>
          <App />
        </AddressProvider>
      </QueryClientProvider>
    </BrowserRouter>
  </StrictMode>
);
```

- [ ] **Step 4: Verify app still loads**

```bash
cd frontend && npm run dev
```

Open `http://localhost:5173` — app should load without errors.

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/lib/queryClient.ts frontend/src/main.tsx
git commit -m "feat: add TanStack Query and QueryClientProvider"
```

---

### Task 2: Replace useRepresentatives with useRepresentativesQuery

**Files:**
- Create: `frontend/src/hooks/useRepresentativesQuery.ts`
- Modify: `frontend/src/pages/RepresentativesPage.tsx`
- Delete: `frontend/src/hooks/useRepresentatives.ts`

- [ ] **Step 1: Create useRepresentativesQuery hook**

Create `frontend/src/hooks/useRepresentativesQuery.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";
import type { Representative, RepresentativesResponse } from "@/types";

const API_URL = import.meta.env.VITE_API_URL;
const STALE_TIME = 5 * 60 * 1000; // 5 minutes

async function fetchRepresentatives(address: string): Promise<Representative[]> {
  const resp = await fetch(`${API_URL}/api/representatives`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ address }),
  });

  if (!resp.ok) {
    const data = await resp.json().catch(() => null);
    throw new Error(data?.detail || `Request failed (${resp.status})`);
  }

  const { representatives }: RepresentativesResponse = await resp.json();
  return representatives;
}

export function useRepresentativesQuery(address: string | null) {
  return useQuery({
    queryKey: ["representatives", address],
    queryFn: () => fetchRepresentatives(address!),
    enabled: !!address,
    staleTime: STALE_TIME,
  });
}
```

- [ ] **Step 2: Update RepresentativesPage to use new hook**

Replace the contents of `frontend/src/pages/RepresentativesPage.tsx`:

```typescript
import { ChevronDown, ChevronRight } from "lucide-react";
import { RepCard } from "@/components/RepCard";
import { SkeletonCard } from "@/components/SkeletonCard";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useRepresentativesQuery } from "@/hooks/useRepresentativesQuery";
import { useResearch } from "@/hooks/useResearch";
import { useAddress } from "@/contexts/AddressContext";
import type { Representative } from "@/types";

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
  return groups.filter((g) => g.reps.length > 0);
}

export function RepresentativesPage() {
  const { address } = useAddress();
  const { data: representatives = [], isLoading, error } = useRepresentativesQuery(address);
  const { requestResearch, getStatus, getSummary } = useResearch();

  const hasResults = representatives.length > 0;
  const groups = groupByLevel(representatives);

  return (
    <>
      {isLoading && !hasResults && (
        <div className="space-y-4">
          <p className="text-center text-sm text-muted-foreground">
            Looking up your representatives…
          </p>
          <div className="grid gap-4 grid-cols-1 max-w-4xl mx-auto">
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="text-center p-6 rounded-lg bg-destructive/10 text-destructive">
          {error.message}
        </div>
      )}

      {hasResults && (
        <div className="space-y-8">
          {groups.map((group) => (
            <Collapsible key={group.level} defaultOpen asChild>
              <section className="max-w-4xl mx-auto">
                <CollapsibleTrigger className="flex w-full items-center gap-2 border-b pb-2 cursor-pointer group">
                  <span className="text-muted-foreground transition-transform group-data-[state=closed]:rotate-0 group-data-[state=open]:rotate-0">
                    <ChevronRight className="h-5 w-5 group-data-[state=open]:hidden" />
                    <ChevronDown className="h-5 w-5 group-data-[state=closed]:hidden" />
                  </span>
                  <h2 className="text-xl font-semibold">
                    {group.label}
                  </h2>
                  <span className="text-sm text-muted-foreground">
                    ({group.reps.length})
                  </span>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <div className="grid gap-4 grid-cols-1 mt-4">
                    {group.reps.map((rep) => (
                      <RepCard
                        key={`${rep.name}-${rep.office}`}
                        rep={rep}
                        researchStatus={getStatus(rep)}
                        summary={getSummary(rep)}
                        onResearch={() => requestResearch(rep)}
                      />
                    ))}
                  </div>
                </CollapsibleContent>
              </section>
            </Collapsible>
          ))}
        </div>
      )}
    </>
  );
}
```

Note: This still imports `useResearch` (the old hook). That gets replaced in Task 4. This is intentional — we migrate one hook at a time so the app stays functional between commits.

- [ ] **Step 3: Delete old hook**

```bash
rm frontend/src/hooks/useRepresentatives.ts
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Verify app works**

```bash
cd frontend && npm run dev
```

Enter an address, verify reps load. Switch to elections tab and back — reps should render instantly from cache.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useRepresentativesQuery.ts frontend/src/pages/RepresentativesPage.tsx
git rm frontend/src/hooks/useRepresentatives.ts
git commit -m "feat: replace useRepresentatives with TanStack Query hook"
```

---

### Task 3: Replace useElections with useElectionsQuery

**Files:**
- Create: `frontend/src/hooks/useElectionsQuery.ts`
- Modify: `frontend/src/pages/ElectionsPage.tsx`
- Delete: `frontend/src/hooks/useElections.ts`

- [ ] **Step 1: Create useElectionsQuery hook**

Create `frontend/src/hooks/useElectionsQuery.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";
import type { Election, ElectionsResponse } from "@/types";

const API_URL = import.meta.env.VITE_API_URL;
const STALE_TIME = 5 * 60 * 1000; // 5 minutes

interface ElectionsResult {
  elections: Election[];
  researchIds: Record<string, string>;
}

async function fetchElections(address: string): Promise<ElectionsResult> {
  const resp = await fetch(`${API_URL}/api/elections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ address }),
  });

  if (!resp.ok) {
    const data = await resp.json().catch(() => null);
    throw new Error(data?.detail || `Request failed (${resp.status})`);
  }

  const data: ElectionsResponse = await resp.json();
  return { elections: data.elections, researchIds: data.research_ids };
}

export function useElectionsQuery(address: string | null) {
  return useQuery({
    queryKey: ["elections", address],
    queryFn: () => fetchElections(address!),
    enabled: !!address,
    staleTime: STALE_TIME,
  });
}
```

- [ ] **Step 2: Update ElectionsPage to use new hook**

Modify `frontend/src/pages/ElectionsPage.tsx` — replace the `useElections` import and usage. The full file:

```typescript
import { useEffect } from "react";
import { useAddress } from "@/contexts/AddressContext";
import { useElectionsQuery } from "@/hooks/useElectionsQuery";
import { useElectionResearch } from "@/hooks/useElectionResearch";
import { useResearch } from "@/hooks/useResearch";
import { ElectionCard } from "@/components/ElectionCard";
import { SkeletonCard } from "@/components/SkeletonCard";
import type { Candidate, Representative } from "@/types";

function candidateToRep(candidate: Candidate): Representative {
  return {
    name: candidate.name,
    office: candidate.office,
    level: candidate.level,
    party: candidate.party,
    photo_url: candidate.photo_url,
    contact: { website: null, phone: null, email: null },
  };
}

export function ElectionsPage() {
  const { address } = useAddress();
  const { data, isLoading, error } = useElectionsQuery(address);
  const elections = data?.elections ?? [];
  const researchIds = data?.researchIds ?? {};
  const { trackElectionResearch, getElectionStatus, getElectionSummary } = useElectionResearch();
  const { requestResearch, getStatus, getSummary } = useResearch();

  // Start polling for auto-triggered election research once we have research IDs
  useEffect(() => {
    for (const [key, researchId] of Object.entries(researchIds)) {
      if (researchId === "cached") continue;
      const [name, date] = key.split("|");
      trackElectionResearch(name, date, researchId);
    }
  }, [researchIds, trackElectionResearch]);

  const handleCandidateResearch = (candidate: Candidate) => {
    requestResearch(candidateToRep(candidate));
  };

  return (
    <>
      {isLoading && (
        <div className="space-y-4">
          <p className="text-center text-sm text-muted-foreground">
            Looking up upcoming elections…
          </p>
          <div className="grid gap-4 grid-cols-1 max-w-4xl mx-auto">
            {Array.from({ length: 2 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="text-center p-6 rounded-lg bg-destructive/10 text-destructive">
          {error.message}
        </div>
      )}

      {!isLoading && elections.length === 0 && !error && (
        <div className="text-center p-8">
          <p className="text-muted-foreground">
            No upcoming elections found for your address.
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            Election data becomes available when election authorities publish ballot information.
          </p>
        </div>
      )}

      {elections.length > 0 && (
        <div className="space-y-6 max-w-4xl mx-auto">
          {elections.map((election) => (
            <ElectionCard
              key={`${election.name}-${election.date}`}
              election={election}
              researchStatus={getElectionStatus(election.name, election.date)}
              researchSummary={getElectionSummary(election.name, election.date)}
              getCandidateResearchStatus={(c) => getStatus(candidateToRep(c))}
              getCandidateResearchSummary={(c) => getSummary(candidateToRep(c))}
              onCandidateResearch={handleCandidateResearch}
            />
          ))}
        </div>
      )}
    </>
  );
}
```

Note: Still imports old `useElectionResearch` and `useResearch`. Replaced in Tasks 4 and 5.

- [ ] **Step 3: Delete old hook**

```bash
rm frontend/src/hooks/useElections.ts
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useElectionsQuery.ts frontend/src/pages/ElectionsPage.tsx
git rm frontend/src/hooks/useElections.ts
git commit -m "feat: replace useElections with TanStack Query hook"
```

---

### Task 4: Replace useResearch with TanStack Query Mutation + Polling

This is the most complex hook. The old hook manages a Map of research entries, manual polling with `setInterval`, and cleanup on unmount. The new version uses `useMutation` to trigger research and individual `useQuery` hooks per rep for polling.

**Design decision:** Since multiple reps can be researched simultaneously and each has independent polling, we use a shared context (`ResearchProvider`) that holds a `Map<string, { researchId, status }>` to coordinate between the mutation (which starts research) and the polling queries (which track progress). This replaces the old `useResearch` hook's internal state.

**Files:**
- Create: `frontend/src/hooks/useResearchQuery.ts`
- Modify: `frontend/src/pages/RepresentativesPage.tsx`
- Modify: `frontend/src/pages/ElectionsPage.tsx`
- Delete: `frontend/src/hooks/useResearch.ts`

- [ ] **Step 1: Create useResearchQuery hook**

Create `frontend/src/hooks/useResearchQuery.ts`:

```typescript
import { useCallback, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { Representative, ResearchSummary, ResearchResponse } from "@/types";

const API_URL = import.meta.env.VITE_API_URL;
const POLL_INTERVAL_MS = 2000;

export type ResearchStatus = "idle" | "loading" | "complete" | "failed";

function repKey(rep: Representative): string {
  return `${rep.name}|${rep.office}`;
}

async function postResearch(rep: Representative): Promise<ResearchResponse> {
  const resp = await fetch(`${API_URL}/api/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ representative: rep }),
  });

  if (!resp.ok) {
    throw new Error(`Research request failed (${resp.status})`);
  }

  return resp.json();
}

async function pollResearch(researchId: string): Promise<ResearchResponse> {
  const resp = await fetch(`${API_URL}/api/research/${researchId}`);
  if (!resp.ok) {
    throw new Error(`Poll failed (${resp.status})`);
  }
  return resp.json();
}

/**
 * Hook for a single representative's research. Call once per rep that needs research.
 * Returns the research state and a function to trigger it.
 */
export function useRepResearch(rep: Representative) {
  const key = repKey(rep);
  const queryClient = useQueryClient();
  const [researchId, setResearchId] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);

  // Polling query — only active when we have a researchId and aren't complete
  const { data: pollData } = useQuery({
    queryKey: ["research", key, researchId],
    queryFn: () => pollResearch(researchId!),
    enabled: polling && !!researchId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "complete" || status === "failed") return false;
      return POLL_INTERVAL_MS;
    },
  });

  // Mutation to start research
  const { mutate: startResearch, isPending: isStarting } = useMutation({
    mutationFn: () => postResearch(rep),
    onSuccess: (data) => {
      if (data.status === "complete" && data.summary) {
        // Cache hit — seed the query cache directly, no polling needed
        queryClient.setQueryData(["research", key, data.research_id], data);
        setResearchId(data.research_id);
        setPolling(false);
      } else {
        // Need to poll
        setResearchId(data.research_id);
        setPolling(true);
        if (data.summary) {
          // Seed with initial partial data
          queryClient.setQueryData(["research", key, data.research_id], data);
        }
      }
    },
  });

  // Stop polling once complete or failed
  const currentData = pollData;
  if (currentData && (currentData.status === "complete" || currentData.status === "failed") && polling) {
    setPolling(false);
  }

  // Derive status
  let status: ResearchStatus = "idle";
  if (isStarting || polling) {
    status = "loading";
  } else if (currentData?.status === "complete") {
    status = "complete";
  } else if (currentData?.status === "failed") {
    status = "failed";
  }

  const summary: ResearchSummary | null = currentData?.summary ?? null;

  return { status, summary, startResearch };
}

/**
 * Convenience hook that provides the same API shape as the old useResearch hook.
 * Manages a map of research entries so multiple reps can be researched from one component.
 */
export function useResearchMap() {
  const [entries, setEntries] = useState<Map<string, {
    researchId: string | null;
    polling: boolean;
  }>>(new Map());
  const queryClient = useQueryClient();

  const requestResearch = useCallback((rep: Representative) => {
    const key = repKey(rep);
    const existing = entries.get(key);
    if (existing) return; // Already started

    setEntries(prev => {
      const next = new Map(prev);
      next.set(key, { researchId: null, polling: false });
      return next;
    });

    postResearch(rep).then(data => {
      if (data.status === "complete" && data.summary) {
        queryClient.setQueryData(["research-map", key], data);
        setEntries(prev => {
          const next = new Map(prev);
          next.set(key, { researchId: data.research_id, polling: false });
          return next;
        });
      } else {
        if (data.summary) {
          queryClient.setQueryData(["research-map", key], data);
        }
        setEntries(prev => {
          const next = new Map(prev);
          next.set(key, { researchId: data.research_id, polling: true });
          return next;
        });
      }
    }).catch(() => {
      queryClient.setQueryData(["research-map", key], {
        research_id: "",
        status: "failed" as const,
        summary: null,
      });
      setEntries(prev => {
        const next = new Map(prev);
        next.set(key, { researchId: null, polling: false });
        return next;
      });
    });
  }, [entries, queryClient]);

  return { requestResearch, entries };
}

/**
 * Hook for polling a single research entry from the map.
 * Used internally — one per active research.
 */
export function useResearchPoll(repKey: string, researchId: string | null, polling: boolean) {
  const queryClient = useQueryClient();

  const { data } = useQuery({
    queryKey: ["research-map", repKey, "poll", researchId],
    queryFn: () => pollResearch(researchId!),
    enabled: polling && !!researchId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "complete" || status === "failed") return false;
      return POLL_INTERVAL_MS;
    },
  });

  // Sync poll results back to the main cache key
  if (data) {
    queryClient.setQueryData(["research-map", repKey], data);
  }

  return data;
}
```

Wait — this is getting complicated. The challenge is that the old `useResearch` hook is used as a single hook that manages *all* reps at once from the page level, but TanStack Query works best with one query per entity. Let me simplify.

**Simpler approach:** Keep a thin coordination layer that uses TanStack Query's `queryClient` directly for caching, but manages polling in a similar way to the old hook. The key insight: we only need TanStack Query's *cache* (so data survives unmount), not necessarily its per-query polling for this case.

Delete the above file and replace with this simpler version:

Create `frontend/src/hooks/useResearchQuery.ts`:

```typescript
import { useCallback, useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { Representative, ResearchSummary, ResearchResponse } from "@/types";

const API_URL = import.meta.env.VITE_API_URL;
const POLL_INTERVAL_MS = 2000;

export type ResearchStatus = "idle" | "loading" | "complete" | "failed";

function repKey(rep: Representative): string {
  return `${rep.name}|${rep.office}`;
}

interface ResearchEntry {
  status: ResearchStatus;
  summary: ResearchSummary | null;
  researchId: string | null;
}

/**
 * Replaces the old useResearch hook. Uses TanStack Query's cache for persistence
 * across route changes, with manual polling for in-progress research.
 */
export function useResearchQuery() {
  const queryClient = useQueryClient();
  const pollTimers = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());

  // Read all research entries from the query cache
  // We use a single query key prefix and read individual entries
  const getEntry = useCallback(
    (key: string): ResearchEntry => {
      return queryClient.getQueryData<ResearchEntry>(["research", key]) ?? {
        status: "idle",
        summary: null,
        researchId: null,
      };
    },
    [queryClient]
  );

  const setEntry = useCallback(
    (key: string, entry: ResearchEntry) => {
      queryClient.setQueryData(["research", key], entry);
    },
    [queryClient]
  );

  // Subscribe to cache changes so the component re-renders
  // We use a dummy query that depends on a counter we increment
  const cacheVersion = useQuery({
    queryKey: ["research-version"],
    queryFn: () => 0,
    initialData: 0,
    staleTime: Infinity,
  });

  const bumpVersion = useCallback(() => {
    queryClient.setQueryData<number>(["research-version"], (v) => (v ?? 0) + 1);
  }, [queryClient]);

  // Clean up poll timers on unmount
  useEffect(() => {
    return () => {
      for (const timer of pollTimers.current.values()) {
        clearInterval(timer);
      }
    };
  }, []);

  const stopPolling = useCallback((key: string) => {
    const timer = pollTimers.current.get(key);
    if (timer) {
      clearInterval(timer);
      pollTimers.current.delete(key);
    }
  }, []);

  const startPolling = useCallback(
    (key: string, researchId: string) => {
      // Don't double-poll
      if (pollTimers.current.has(key)) return;

      const timer = setInterval(async () => {
        try {
          const resp = await fetch(`${API_URL}/api/research/${researchId}`);
          if (!resp.ok) {
            stopPolling(key);
            setEntry(key, { status: "failed", summary: null, researchId });
            bumpVersion();
            return;
          }

          const data: ResearchResponse = await resp.json();
          if (data.status === "complete") {
            stopPolling(key);
            setEntry(key, { status: "complete", summary: data.summary, researchId });
            bumpVersion();
          } else if (data.status === "in_progress" || data.status === "pending") {
            if (data.summary) {
              setEntry(key, { status: "loading", summary: data.summary, researchId });
              bumpVersion();
            }
          } else if (data.status === "failed") {
            stopPolling(key);
            setEntry(key, { status: "failed", summary: null, researchId });
            bumpVersion();
          }
        } catch {
          // Network error — keep polling
        }
      }, POLL_INTERVAL_MS);

      pollTimers.current.set(key, timer);
    },
    [stopPolling, setEntry, bumpVersion]
  );

  const requestResearch = useCallback(
    (rep: Representative) => {
      const key = repKey(rep);
      const existing = getEntry(key);
      if (existing.status === "loading" || existing.status === "complete") return;

      setEntry(key, { status: "loading", summary: null, researchId: null });
      bumpVersion();

      (async () => {
        try {
          const resp = await fetch(`${API_URL}/api/research`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ representative: rep }),
          });

          if (!resp.ok) {
            setEntry(key, { status: "failed", summary: null, researchId: null });
            bumpVersion();
            return;
          }

          const data: ResearchResponse = await resp.json();

          if (data.status === "complete" && data.summary) {
            setEntry(key, { status: "complete", summary: data.summary, researchId: data.research_id });
            bumpVersion();
            return;
          }

          if (data.summary) {
            setEntry(key, { status: "loading", summary: data.summary, researchId: data.research_id });
            bumpVersion();
          }

          startPolling(key, data.research_id);
        } catch {
          setEntry(key, { status: "failed", summary: null, researchId: null });
          bumpVersion();
        }
      })();
    },
    [getEntry, setEntry, bumpVersion, startPolling]
  );

  const getStatus = useCallback(
    (rep: Representative): ResearchStatus => {
      // Read cacheVersion.data to establish reactive dependency
      void cacheVersion.data;
      return getEntry(repKey(rep)).status;
    },
    [getEntry, cacheVersion.data]
  );

  const getSummary = useCallback(
    (rep: Representative): ResearchSummary | null => {
      void cacheVersion.data;
      return getEntry(repKey(rep)).summary;
    },
    [getEntry, cacheVersion.data]
  );

  return { requestResearch, getStatus, getSummary };
}
```

- [ ] **Step 2: Update RepresentativesPage to import new hook**

In `frontend/src/pages/RepresentativesPage.tsx`, change the import:

```typescript
// Old:
import { useResearch } from "@/hooks/useResearch";

// New:
import { useResearchQuery as useResearch } from "@/hooks/useResearchQuery";
```

The hook returns the same shape (`requestResearch`, `getStatus`, `getSummary`), so no other changes needed.

- [ ] **Step 3: Update ElectionsPage to import new hook**

In `frontend/src/pages/ElectionsPage.tsx`, change the import:

```typescript
// Old:
import { useResearch } from "@/hooks/useResearch";

// New:
import { useResearchQuery as useResearch } from "@/hooks/useResearchQuery";
```

- [ ] **Step 4: Delete old hook**

```bash
rm frontend/src/hooks/useResearch.ts
```

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 6: Verify research works**

```bash
cd frontend && npm run dev
```

Enter an address, click "Research" on a rep. Verify:
1. Sections appear incrementally as before
2. Switch tabs and back — research results persist
3. Research a candidate on elections tab — if same person is on reps tab, research shows there too

- [ ] **Step 7: Commit**

```bash
git add frontend/src/hooks/useResearchQuery.ts frontend/src/pages/RepresentativesPage.tsx frontend/src/pages/ElectionsPage.tsx
git rm frontend/src/hooks/useResearch.ts
git commit -m "feat: replace useResearch with TanStack Query-backed hook"
```

---

### Task 5: Replace useElectionResearch with TanStack Query-backed Hook

**Files:**
- Create: `frontend/src/hooks/useElectionResearchQuery.ts`
- Modify: `frontend/src/pages/ElectionsPage.tsx`
- Delete: `frontend/src/hooks/useElectionResearch.ts`

- [ ] **Step 1: Create useElectionResearchQuery hook**

Create `frontend/src/hooks/useElectionResearchQuery.ts`:

```typescript
import { useCallback, useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { ElectionResearchSummary, ElectionResearchResponse } from "@/types";

const API_URL = import.meta.env.VITE_API_URL;
const POLL_INTERVAL_MS = 2000;

export type ElectionResearchStatus = "idle" | "loading" | "complete" | "failed";

function electionKey(name: string, date: string): string {
  return `${name}|${date}`;
}

interface ElectionResearchEntry {
  status: ElectionResearchStatus;
  researchId: string | null;
  summary: ElectionResearchSummary | null;
}

export function useElectionResearchQuery() {
  const queryClient = useQueryClient();
  const pollTimers = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());

  const getEntry = useCallback(
    (key: string): ElectionResearchEntry => {
      return queryClient.getQueryData<ElectionResearchEntry>(["election-research", key]) ?? {
        status: "idle",
        researchId: null,
        summary: null,
      };
    },
    [queryClient]
  );

  const setEntry = useCallback(
    (key: string, entry: ElectionResearchEntry) => {
      queryClient.setQueryData(["election-research", key], entry);
    },
    [queryClient]
  );

  const cacheVersion = useQuery({
    queryKey: ["election-research-version"],
    queryFn: () => 0,
    initialData: 0,
    staleTime: Infinity,
  });

  const bumpVersion = useCallback(() => {
    queryClient.setQueryData<number>(["election-research-version"], (v) => (v ?? 0) + 1);
  }, [queryClient]);

  useEffect(() => {
    return () => {
      for (const timer of pollTimers.current.values()) {
        clearInterval(timer);
      }
    };
  }, []);

  const stopPolling = useCallback((key: string) => {
    const timer = pollTimers.current.get(key);
    if (timer) {
      clearInterval(timer);
      pollTimers.current.delete(key);
    }
  }, []);

  const startPolling = useCallback(
    (key: string, researchId: string) => {
      if (pollTimers.current.has(key)) return;

      const timer = setInterval(async () => {
        try {
          const resp = await fetch(`${API_URL}/api/election-research/${researchId}`);
          if (!resp.ok) {
            stopPolling(key);
            setEntry(key, { status: "failed", researchId, summary: null });
            bumpVersion();
            return;
          }

          const data: ElectionResearchResponse = await resp.json();
          if (data.status === "complete") {
            stopPolling(key);
            setEntry(key, { status: "complete", researchId, summary: data.summary });
            bumpVersion();
          } else if (data.status === "in_progress" || data.status === "pending") {
            if (data.summary) {
              setEntry(key, { status: "loading", researchId, summary: data.summary });
              bumpVersion();
            }
          } else if (data.status === "failed") {
            stopPolling(key);
            setEntry(key, { status: "failed", researchId, summary: null });
            bumpVersion();
          }
        } catch {
          // Network error — keep polling
        }
      }, POLL_INTERVAL_MS);

      pollTimers.current.set(key, timer);
    },
    [stopPolling, setEntry, bumpVersion]
  );

  const trackElectionResearch = useCallback(
    (electionName: string, electionDate: string, researchId: string) => {
      const key = electionKey(electionName, electionDate);
      const existing = getEntry(key);
      if (existing.status === "complete" || existing.status === "loading") return;

      setEntry(key, { status: "loading", researchId, summary: null });
      bumpVersion();
      startPolling(key, researchId);
    },
    [getEntry, setEntry, bumpVersion, startPolling]
  );

  const getElectionStatus = useCallback(
    (electionName: string, electionDate: string): ElectionResearchStatus => {
      void cacheVersion.data;
      return getEntry(electionKey(electionName, electionDate)).status;
    },
    [getEntry, cacheVersion.data]
  );

  const getElectionSummary = useCallback(
    (electionName: string, electionDate: string): ElectionResearchSummary | null => {
      void cacheVersion.data;
      return getEntry(electionKey(electionName, electionDate)).summary;
    },
    [getEntry, cacheVersion.data]
  );

  return { trackElectionResearch, getElectionStatus, getElectionSummary };
}
```

- [ ] **Step 2: Update ElectionsPage to import new hook**

In `frontend/src/pages/ElectionsPage.tsx`, change the import:

```typescript
// Old:
import { useElectionResearch } from "@/hooks/useElectionResearch";

// New:
import { useElectionResearchQuery as useElectionResearch } from "@/hooks/useElectionResearchQuery";
```

No other changes needed — the hook returns the same shape.

- [ ] **Step 3: Delete old hook**

```bash
rm frontend/src/hooks/useElectionResearch.ts
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useElectionResearchQuery.ts frontend/src/pages/ElectionsPage.tsx
git rm frontend/src/hooks/useElectionResearch.ts
git commit -m "feat: replace useElectionResearch with TanStack Query-backed hook"
```

---

### Task 6: Verify Complete Migration and Clean Up

**Files:**
- Check: all files in `frontend/src/hooks/`

- [ ] **Step 1: Verify no imports of old hooks remain**

```bash
cd frontend && grep -r "useRepresentatives\b" src/ --include="*.ts" --include="*.tsx" | grep -v "useRepresentativesQuery"
grep -r "useElections\b" src/ --include="*.ts" --include="*.tsx" | grep -v "useElectionsQuery"
grep -r "from.*useResearch\b" src/ --include="*.ts" --include="*.tsx" | grep -v "useResearchQuery"
grep -r "from.*useElectionResearch\b" src/ --include="*.ts" --include="*.tsx" | grep -v "useElectionResearchQuery"
```

Expected: no output (no stale imports).

- [ ] **Step 2: Verify old hook files are deleted**

```bash
ls frontend/src/hooks/
```

Expected: `useRepresentativesQuery.ts`, `useElectionsQuery.ts`, `useResearchQuery.ts`, `useElectionResearchQuery.ts` — no old files.

- [ ] **Step 3: Full build check**

```bash
cd frontend && npm run build
```

Expected: builds successfully with no errors.

- [ ] **Step 4: Full manual smoke test**

```bash
cd frontend && npm run dev
```

Test the following:
1. Enter address on `/` — navigates to `/reps`, reps load
2. Click "Research" on a federal rep — sections fill in incrementally
3. Switch to `/elections` tab — elections load (reps page data preserved)
4. Switch back to `/reps` — instant render, no spinner, research results still there
5. On `/elections`, trigger candidate research — switch to `/reps` and back, research persists
6. Enter a new address — fresh data loads for both tabs

- [ ] **Step 5: Lint check**

```bash
cd frontend && npm run lint
```

Expected: no new lint errors.
