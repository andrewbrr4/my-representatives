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
    const timers = pollTimers.current;
    return () => {
      for (const timer of timers.values()) {
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
