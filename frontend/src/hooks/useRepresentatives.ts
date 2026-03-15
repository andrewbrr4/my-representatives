import { useState, useCallback, useRef, useEffect } from "react";
import type { Representative, LookupResponse, JobStatusResponse } from "@/types";

const API_URL = import.meta.env.VITE_API_URL;
const POLL_INTERVAL_MS = 2000;

export function useRepresentatives() {
  const [representatives, setRepresentatives] = useState<Representative[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const deliveredRef = useRef<Set<number>>(new Set());

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  // Clean up polling on unmount
  useEffect(() => {
    return () => {
      stopPolling();
      abortRef.current?.abort();
    };
  }, [stopPolling]);

  const startPolling = useCallback((jobId: string) => {
    stopPolling();
    pollTimerRef.current = setInterval(async () => {
      try {
        const resp = await fetch(`${API_URL}/api/jobs/${jobId}`);
        if (resp.status === 404) {
          stopPolling();
          setError("Session expired. Please search again.");
          setLoading(false);
          return;
        }
        if (!resp.ok) return; // retry on next interval

        const job: JobStatusResponse = await resp.json();

        if (job.research) {
          for (const entry of job.research) {
            if (
              !deliveredRef.current.has(entry.index) &&
              (entry.status === "complete" || entry.status === "failed")
            ) {
              deliveredRef.current.add(entry.index);
              const summary = entry.summary;
              setRepresentatives((prev) => {
                const updated = [...prev];
                updated[entry.index] = { ...updated[entry.index], summary };
                return updated;
              });
            }
          }
        }

        if (job.status === "done" || job.status === "error") {
          stopPolling();
          if (job.status === "error" && job.error_detail) {
            setError(job.error_detail);
          }
          setLoading(false);
        }
      } catch {
        // Network error — keep polling
      }
    }, POLL_INTERVAL_MS);
  }, [stopPolling]);

  const lookup = useCallback(async (address: string) => {
    // Abort any in-flight request and stop existing polling
    abortRef.current?.abort();
    stopPolling();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);
    setRepresentatives([]);
    deliveredRef.current = new Set();

    try {
      const resp = await fetch(`${API_URL}/api/representatives`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address }),
        signal: controller.signal,
      });

      if (!resp.ok) {
        const data = await resp.json().catch(() => null);
        throw new Error(data?.detail || `Request failed (${resp.status})`);
      }

      const { job_id, representatives }: LookupResponse = await resp.json();

      // Set reps immediately (without summaries)
      setRepresentatives(
        representatives.map((r) => ({ ...r, summary: undefined }))
      );

      // Start polling for research results
      startPolling(job_id);
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setLoading(false);
    }
  }, [startPolling, stopPolling]);

  return { representatives, loading, error, lookup };
}
