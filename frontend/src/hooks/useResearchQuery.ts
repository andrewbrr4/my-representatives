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
