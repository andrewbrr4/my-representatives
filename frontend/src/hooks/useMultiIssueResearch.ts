import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type {
  Representative,
  IssueResearchResponse,
  IssueStanceSummary,
  IssueInfo,
} from "@/types";

const API_URL = import.meta.env.VITE_API_URL;
const POLL_INTERVAL_MS = 2000;

export type CompareStatus = "idle" | "matching" | "researching" | "done";

export interface RepResult {
  status: "loading" | "complete" | "failed";
  summary: IssueStanceSummary | null;
}

function cacheKey(rep: Representative, issueId: string): string {
  return `${rep.name}|${rep.office}|${issueId}`;
}

interface IssueEntry {
  status: "idle" | "loading" | "complete" | "failed";
  summary: IssueStanceSummary | null;
  researchId: string | null;
  issue: IssueInfo | null;
}

export function useMultiIssueResearch() {
  const queryClient = useQueryClient();
  const pollTimers = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());
  const mountedRef = useRef(false);

  const [compareStatus, setCompareStatus] = useState<CompareStatus>("idle");
  const [matchedIssue, setMatchedIssue] = useState<IssueInfo | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [selectedReps, setSelectedReps] = useState<Representative[]>([]);
  // Incremented to trigger re-renders when cache entries change
  const [version, setVersion] = useState(0);

  const bumpVersion = useCallback(() => setVersion((v) => v + 1), []);

  const getEntry = useCallback(
    (key: string): IssueEntry => {
      return queryClient.getQueryData<IssueEntry>(["issue-research", key]) ?? {
        status: "idle",
        summary: null,
        researchId: null,
        issue: null,
      };
    },
    [queryClient],
  );

  const setEntry = useCallback(
    (key: string, entry: IssueEntry) => {
      queryClient.setQueryData(["issue-research", key], entry);
    },
    [queryClient],
  );

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
      if (!mountedRef.current) return;

      const timer = setInterval(async () => {
        try {
          const resp = await fetch(`${API_URL}/api/issue-research/${researchId}`);
          if (!resp.ok) {
            stopPolling(key);
            const prev = getEntry(key);
            setEntry(key, { ...prev, status: "failed", researchId });
            bumpVersion();
            return;
          }

          const data: IssueResearchResponse = await resp.json();
          const prev = getEntry(key);
          if (data.status === "complete") {
            stopPolling(key);
            setEntry(key, { ...prev, status: "complete", summary: data.summary, researchId });
            bumpVersion();
          } else if (data.status === "in_progress" || data.status === "pending") {
            if (data.summary) {
              setEntry(key, { ...prev, status: "loading", summary: data.summary, researchId });
              bumpVersion();
            }
          } else if (data.status === "failed") {
            stopPolling(key);
            setEntry(key, { ...prev, status: "failed", researchId });
            bumpVersion();
          }
        } catch {
          // Network error — keep polling
        }
      }, POLL_INTERVAL_MS);

      pollTimers.current.set(key, timer);
    },
    [stopPolling, getEntry, setEntry, bumpVersion],
  );

  // Clean up polling on unmount
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      for (const timer of pollTimers.current.values()) {
        clearInterval(timer);
      }
      pollTimers.current.clear();
    };
  }, []);

  // Check if all selected reps are done whenever version changes
  useEffect(() => {
    if (compareStatus !== "researching" || !matchedIssue || selectedReps.length === 0) return;
    const allDone = selectedReps.every((rep) => {
      const entry = getEntry(cacheKey(rep, matchedIssue.id));
      return entry.status === "complete" || entry.status === "failed";
    });
    if (allDone) setCompareStatus("done");
  }, [version, compareStatus, matchedIssue, selectedReps, getEntry]);

  const handleRepResponse = useCallback(
    (rep: Representative, issueInfo: IssueInfo, data: IssueResearchResponse) => {
      const key = cacheKey(rep, issueInfo.id);

      if (data.status === "complete" && data.summary) {
        setEntry(key, {
          status: "complete",
          summary: data.summary,
          researchId: data.research_id,
          issue: issueInfo,
        });
        bumpVersion();
        return;
      }

      setEntry(key, {
        status: "loading",
        summary: data.summary ?? null,
        researchId: data.research_id,
        issue: issueInfo,
      });
      bumpVersion();
      if (data.research_id) {
        startPolling(key, data.research_id);
      }
    },
    [setEntry, bumpVersion, startPolling],
  );

  const compareIssue = useCallback(
    async (query: string, reps: Representative[]) => {
      setErrorMessage(null);
      setMatchedIssue(null);
      setSelectedReps(reps);
      setCompareStatus("matching");

      // Step 1: Fire the first rep to classify the issue + start its research
      let firstData: IssueResearchResponse;
      try {
        const resp = await fetch(`${API_URL}/api/issue-research`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ representative: reps[0], query }),
        });
        if (!resp.ok) {
          setCompareStatus("idle");
          setErrorMessage("Something went wrong. Try again.");
          return;
        }
        firstData = await resp.json();
      } catch {
        setCompareStatus("idle");
        setErrorMessage("Network error. Check your connection.");
        return;
      }

      if (firstData.status === "no_match") {
        setCompareStatus("idle");
        setErrorMessage(
          firstData.message || "Couldn't match that to a political issue.",
        );
        return;
      }

      const issueInfo = firstData.issue!;
      setMatchedIssue(issueInfo);
      setCompareStatus("researching");

      // Handle first rep's response (may already be cached/complete)
      handleRepResponse(reps[0], issueInfo, firstData);

      // Step 2: Fire remaining reps in parallel
      if (reps.length > 1) {
        const remaining = reps.slice(1);
        const results = await Promise.allSettled(
          remaining.map(async (rep) => {
            // Check client cache first
            const key = cacheKey(rep, issueInfo.id);
            const existing = getEntry(key);
            if (existing.status === "complete") return;
            if (existing.status === "loading" && existing.researchId) {
              handleRepResponse(rep, issueInfo, {
                researchId: existing.researchId,
                summary: existing.summary,
              } as IssueResearchResponse);
              return;
            }

            const resp = await fetch(`${API_URL}/api/issue-research`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ representative: rep, query }),
            });
            if (!resp.ok) {
              setEntry(key, { status: "failed", summary: null, researchId: null, issue: issueInfo });
              bumpVersion();
              return;
            }
            const data: IssueResearchResponse = await resp.json();
            handleRepResponse(rep, issueInfo, data);
          }),
        );

        // Log rejected promises
        for (const r of results) {
          if (r.status === "rejected") {
            console.error("Issue research request failed:", r.reason);
          }
        }
      }
    },
    [handleRepResponse, getEntry, setEntry, bumpVersion],
  );

  const getResult = useCallback(
    (rep: Representative): RepResult => {
      // Read version to subscribe to updates
      void version;
      if (!matchedIssue) return { status: "loading", summary: null };
      const entry = getEntry(cacheKey(rep, matchedIssue.id));
      if (entry.status === "complete") return { status: "complete", summary: entry.summary };
      if (entry.status === "failed") return { status: "failed", summary: null };
      return { status: "loading", summary: entry.summary };
    },
    [matchedIssue, getEntry, version],
  );

  const retryRep = useCallback(
    async (rep: Representative, query: string) => {
      if (!matchedIssue) return;
      const key = cacheKey(rep, matchedIssue.id);
      setEntry(key, { status: "loading", summary: null, researchId: null, issue: matchedIssue });
      bumpVersion();
      if (compareStatus === "done") setCompareStatus("researching");

      try {
        const resp = await fetch(`${API_URL}/api/issue-research`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ representative: rep, query }),
        });
        if (!resp.ok) {
          setEntry(key, { status: "failed", summary: null, researchId: null, issue: matchedIssue });
          bumpVersion();
          return;
        }
        const data: IssueResearchResponse = await resp.json();
        handleRepResponse(rep, matchedIssue, data);
      } catch {
        setEntry(key, { status: "failed", summary: null, researchId: null, issue: matchedIssue });
        bumpVersion();
      }
    },
    [matchedIssue, compareStatus, setEntry, bumpVersion, handleRepResponse],
  );

  return {
    compareStatus,
    matchedIssue,
    errorMessage,
    compareIssue,
    getResult,
    retryRep,
  };
}
