import { useState, useCallback, useRef } from "react";
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

function updateEntry(
  key: string,
  entry: ElectionResearchEntry,
): (prev: Map<string, ElectionResearchEntry>) => Map<string, ElectionResearchEntry> {
  return (prev) => {
    const next = new Map(prev);
    next.set(key, entry);
    return next;
  };
}

export function useElectionResearch() {
  const [entries, setEntries] = useState<Map<string, ElectionResearchEntry>>(new Map());
  const entriesRef = useRef(entries);
  entriesRef.current = entries;
  const pollTimers = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());

  const stopPolling = useCallback((key: string) => {
    const timer = pollTimers.current.get(key);
    if (timer) {
      clearInterval(timer);
      pollTimers.current.delete(key);
    }
  }, []);

  const startPolling = useCallback(
    (key: string, researchId: string) => {
      const timer = setInterval(async () => {
        try {
          const resp = await fetch(`${API_URL}/api/election-research/${researchId}`);
          if (!resp.ok) {
            stopPolling(key);
            setEntries(updateEntry(key, { status: "failed", researchId, summary: null }));
            return;
          }

          const data: ElectionResearchResponse = await resp.json();
          if (data.status === "complete") {
            stopPolling(key);
            setEntries(updateEntry(key, { status: "complete", researchId, summary: data.summary }));
          } else if (data.status === "in_progress" || data.status === "pending") {
            if (data.summary) {
              setEntries(updateEntry(key, { status: "loading", researchId, summary: data.summary }));
            }
          } else if (data.status === "failed") {
            stopPolling(key);
            setEntries(updateEntry(key, { status: "failed", researchId, summary: null }));
          }
        } catch {
          // Network error — keep polling
        }
      }, POLL_INTERVAL_MS);

      pollTimers.current.set(key, timer);
    },
    [stopPolling]
  );

  const trackElectionResearch = useCallback(
    (electionName: string, electionDate: string, researchId: string) => {
      const key = electionKey(electionName, electionDate);
      const existing = entriesRef.current.get(key);
      if (existing && (existing.status === "complete" || existing.status === "loading")) return;

      setEntries(updateEntry(key, { status: "loading", researchId, summary: null }));
      startPolling(key, researchId);
    },
    [startPolling]
  );

  const getElectionStatus = useCallback(
    (electionName: string, electionDate: string): ElectionResearchStatus => {
      return entries.get(electionKey(electionName, electionDate))?.status ?? "idle";
    },
    [entries]
  );

  const getElectionSummary = useCallback(
    (electionName: string, electionDate: string): ElectionResearchSummary | null => {
      return entries.get(electionKey(electionName, electionDate))?.summary ?? null;
    },
    [entries]
  );

  return { trackElectionResearch, getElectionStatus, getElectionSummary };
}
