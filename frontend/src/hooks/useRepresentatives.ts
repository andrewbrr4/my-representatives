import { useState, useCallback, useRef } from "react";
import type { Representative, ResearchSummary, JobStatusResponse } from "@/types";

const API_URL = import.meta.env.VITE_API_URL || "https://my-reps-backend-968920716189.us-east1.run.app";
const POLL_INTERVAL_MS = 2000;

export function useRepresentatives() {
  const [representatives, setRepresentatives] = useState<Representative[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const jobIdRef = useRef<string | null>(null);
  const deliveredRef = useRef<Set<number>>(new Set());
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

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
    // Abort any in-flight request
    abortRef.current?.abort();
    stopPolling();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);
    setRepresentatives([]);
    jobIdRef.current = null;
    deliveredRef.current = new Set();

    let receivedDone = false;

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

      const reader = resp.body?.getReader();
      if (!reader) throw new Error("Streaming not supported");

      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("event:")) {
            currentEvent = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            const data = line.slice(5).trim();
            handleSSEEvent(currentEvent, data);
          }
        }
      }

      // Process any remaining buffer
      if (buffer.trim()) {
        const lines = buffer.split("\n");
        for (const line of lines) {
          if (line.startsWith("event:")) {
            currentEvent = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            const data = line.slice(5).trim();
            handleSSEEvent(currentEvent, data);
          }
        }
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") return;

      // If we have a job ID and the stream broke, fall back to polling
      if (jobIdRef.current && !receivedDone) {
        startPolling(jobIdRef.current);
        return;
      }

      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      // If stream ended without a done event but we have a job, start polling
      if (!receivedDone && jobIdRef.current) {
        startPolling(jobIdRef.current);
      } else {
        setLoading(false);
      }
    }

    function handleSSEEvent(event: string, data: string) {
      if (event === "representatives") {
        const parsed = JSON.parse(data);
        setRepresentatives(
          parsed.representatives.map((r: Representative) => ({ ...r, summary: undefined }))
        );
      } else if (event === "job") {
        const { job_id } = JSON.parse(data);
        jobIdRef.current = job_id;
      } else if (event === "research") {
        const { index, summary } = JSON.parse(data) as {
          index: number;
          summary: ResearchSummary | null;
        };
        deliveredRef.current.add(index);
        setRepresentatives((prev) => {
          const updated = [...prev];
          updated[index] = { ...updated[index], summary };
          return updated;
        });
      } else if (event === "done") {
        receivedDone = true;
        setLoading(false);
      } else if (event === "error") {
        const parsed = JSON.parse(data);
        setError(parsed.detail);
      }
    }
  }, [startPolling, stopPolling]);

  return { representatives, loading, error, lookup };
}
