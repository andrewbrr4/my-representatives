import { useCallback, useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  Representative,
  IssueMatchResponse,
  IssueResearchResponse,
  IssueStanceSummary,
  IssueInfo,
} from "@/types";

const API_URL = import.meta.env.VITE_API_URL;
const POLL_INTERVAL_MS = 2000;

export type IssueResearchStatus = "idle" | "matching" | "loading" | "complete" | "failed";

function issueKey(rep: Representative, issueId: string): string {
  return `${rep.name}|${rep.office}|${issueId}`;
}

interface IssueEntry {
  status: IssueResearchStatus;
  summary: IssueStanceSummary | null;
  researchId: string | null;
  issue: IssueInfo | null;
}

export function useIssueSearch(rep: Representative) {
  const queryClient = useQueryClient();
  const pollTimers = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());
  const mountedRef = useRef(false);

  const getEntry = useCallback(
    (key: string): IssueEntry => {
      return queryClient.getQueryData<IssueEntry>(["issue-research", key]) ?? {
        status: "idle",
        summary: null,
        researchId: null,
        issue: null,
      };
    },
    [queryClient]
  );

  const setEntry = useCallback(
    (key: string, entry: IssueEntry) => {
      queryClient.setQueryData(["issue-research", key], entry);
    },
    [queryClient]
  );

  // Version bump to trigger re-renders
  const cacheVersion = useQuery({
    queryKey: ["issue-research-version", rep.name, rep.office],
    queryFn: () => 0,
    initialData: 0,
    staleTime: Infinity,
  });

  const bumpVersion = useCallback(() => {
    queryClient.setQueryData<number>(
      ["issue-research-version", rep.name, rep.office],
      (v) => (v ?? 0) + 1
    );
  }, [queryClient, rep.name, rep.office]);

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
    [stopPolling, getEntry, setEntry, bumpVersion]
  );

  // Restart polling on mount, clean up on unmount
  useEffect(() => {
    mountedRef.current = true;
    const cache = queryClient.getQueryCache().getAll();
    for (const query of cache) {
      const qk = query.queryKey;
      if (qk[0] === "issue-research" && qk.length === 2 && typeof qk[1] === "string") {
        const entry = query.state.data as IssueEntry | undefined;
        if (entry?.status === "loading" && entry.researchId) {
          startPolling(qk[1], entry.researchId);
        }
      }
    }
    return () => {
      mountedRef.current = false;
      for (const timer of pollTimers.current.values()) {
        clearInterval(timer);
      }
      pollTimers.current.clear();
    };
  }, [queryClient, startPolling]);

  /** Search for an issue and kick off research. Returns error message or null. */
  const searchIssue = useCallback(
    async (query: string): Promise<string | null> => {
      // Step 1: match the query to an issue
      try {
        const matchResp = await fetch(`${API_URL}/api/issue-match`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query }),
        });

        if (!matchResp.ok) return "Something went wrong. Try again.";

        const matchData: IssueMatchResponse = await matchResp.json();
        if (!matchData.matched || !matchData.issue) {
          return matchData.message || "Couldn't match that to a political issue.";
        }

        const issue = matchData.issue;
        const key = issueKey(rep, issue.id);

        // Check if we already have this issue researched
        const existing = getEntry(key);
        if (existing.status === "complete" || existing.status === "loading") {
          return null; // already done or in progress
        }

        // Step 2: start issue research
        setEntry(key, { status: "loading", summary: null, researchId: null, issue });
        bumpVersion();

        const researchResp = await fetch(`${API_URL}/api/issue-research`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            representative: rep,
            issue_id: issue.id,
            issue_label: issue.label,
          }),
        });

        if (!researchResp.ok) {
          setEntry(key, { status: "failed", summary: null, researchId: null, issue });
          bumpVersion();
          return "Research request failed. Try again.";
        }

        const researchData: IssueResearchResponse = await researchResp.json();

        if (researchData.status === "complete" && researchData.summary) {
          setEntry(key, {
            status: "complete",
            summary: researchData.summary,
            researchId: researchData.research_id,
            issue,
          });
          bumpVersion();
          return null;
        }

        setEntry(key, {
          status: "loading",
          summary: researchData.summary ?? null,
          researchId: researchData.research_id,
          issue,
        });
        bumpVersion();
        startPolling(key, researchData.research_id);
        return null;
      } catch {
        return "Network error. Check your connection.";
      }
    },
    [rep, getEntry, setEntry, bumpVersion, startPolling]
  );

  /** Get all issue entries for this rep. */
  const getIssueEntries = useCallback((): { key: string; entry: IssueEntry }[] => {
    void cacheVersion.data;
    const results: { key: string; entry: IssueEntry }[] = [];
    const prefix = `${rep.name}|${rep.office}|`;
    const cache = queryClient.getQueryCache().getAll();
    for (const query of cache) {
      const qk = query.queryKey;
      if (qk[0] === "issue-research" && qk.length === 2 && typeof qk[1] === "string") {
        const k = qk[1] as string;
        if (k.startsWith(prefix)) {
          const entry = query.state.data as IssueEntry | undefined;
          if (entry) results.push({ key: k, entry });
        }
      }
    }
    return results;
  }, [queryClient, rep.name, rep.office, cacheVersion.data]);

  return { searchIssue, getIssueEntries };
}
