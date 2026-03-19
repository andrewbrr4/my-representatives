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

export function useResearch() {
  const [entries, setEntries] = useState<Map<string, ResearchEntry>>(new Map());
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
    const existing = entries.get(key);
    if (existing && (existing.status === "loading" || existing.status === "complete")) {
      return;
    }

    setEntries((prev) => {
      const next = new Map(prev);
      next.set(key, { status: "loading", summary: null });
      return next;
    });

    (async () => {
      try {
        const resp = await fetch(`${API_URL}/api/research`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ representative: rep }),
        });

        if (!resp.ok) {
          setEntries((prev) => {
            const next = new Map(prev);
            next.set(key, { status: "failed", summary: null });
            return next;
          });
          return;
        }

        const data: ResearchResponse = await resp.json();

        if (data.status === "complete" && data.summary) {
          setEntries((prev) => {
            const next = new Map(prev);
            next.set(key, { status: "complete", summary: data.summary });
            return next;
          });
          return;
        }

        // Poll for completion
        const timer = setInterval(async () => {
          try {
            const pollResp = await fetch(`${API_URL}/api/research/${data.research_id}`);
            if (!pollResp.ok) {
              stopPolling(key);
              setEntries((prev) => {
                const next = new Map(prev);
                next.set(key, { status: "failed", summary: null });
                return next;
              });
              return;
            }

            const pollData: ResearchResponse = await pollResp.json();
            if (pollData.status === "complete") {
              stopPolling(key);
              setEntries((prev) => {
                const next = new Map(prev);
                next.set(key, { status: "complete", summary: pollData.summary });
                return next;
              });
            } else if (pollData.status === "failed") {
              stopPolling(key);
              setEntries((prev) => {
                const next = new Map(prev);
                next.set(key, { status: "failed", summary: null });
                return next;
              });
            }
          } catch {
            // Network error — keep polling
          }
        }, POLL_INTERVAL_MS);

        pollTimers.current.set(key, timer);
      } catch {
        setEntries((prev) => {
          const next = new Map(prev);
          next.set(key, { status: "failed", summary: null });
          return next;
        });
      }
    })();
  }, [entries, stopPolling]);

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
