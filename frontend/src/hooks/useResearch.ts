import { useState, useCallback, useRef } from "react";
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
}

function updateEntry(
  key: string,
  entry: ResearchEntry,
): (prev: Map<string, ResearchEntry>) => Map<string, ResearchEntry> {
  return (prev) => {
    const next = new Map(prev);
    next.set(key, entry);
    return next;
  };
}

export function useResearch() {
  const [entries, setEntries] = useState<Map<string, ResearchEntry>>(new Map());
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

  const requestResearch = useCallback((rep: Representative) => {
    const key = repKey(rep);

    // Don't re-request if already loading or complete
    const existing = entriesRef.current.get(key);
    if (existing && (existing.status === "loading" || existing.status === "complete")) {
      return;
    }

    setEntries(updateEntry(key, { status: "loading", summary: null }));

    (async () => {
      try {
        const resp = await fetch(`${API_URL}/api/research`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ representative: rep }),
        });

        if (!resp.ok) {
          setEntries(updateEntry(key, { status: "failed", summary: null }));
          return;
        }

        const data: ResearchResponse = await resp.json();

        if (data.status === "complete" && data.summary) {
          setEntries(updateEntry(key, { status: "complete", summary: data.summary }));
          return;
        }

        // Poll for completion
        const timer = setInterval(async () => {
          try {
            const pollResp = await fetch(`${API_URL}/api/research/${data.research_id}`);
            if (!pollResp.ok) {
              stopPolling(key);
              setEntries(updateEntry(key, { status: "failed", summary: null }));
              return;
            }

            const pollData: ResearchResponse = await pollResp.json();
            if (pollData.status === "complete") {
              stopPolling(key);
              setEntries(updateEntry(key, { status: "complete", summary: pollData.summary }));
            } else if (pollData.status === "failed") {
              stopPolling(key);
              setEntries(updateEntry(key, { status: "failed", summary: null }));
            }
          } catch {
            // Network error — keep polling
          }
        }, POLL_INTERVAL_MS);

        pollTimers.current.set(key, timer);
      } catch {
        setEntries(updateEntry(key, { status: "failed", summary: null }));
      }
    })();
  }, [stopPolling]);

  const getStatus = useCallback(
    (rep: Representative): ResearchStatus => {
      return entries.get(repKey(rep))?.status ?? "idle";
    },
    [entries]
  );

  const getSummary = useCallback(
    (rep: Representative): ResearchSummary | null => {
      return entries.get(repKey(rep))?.summary ?? null;
    },
    [entries]
  );

  return { requestResearch, getStatus, getSummary };
}
