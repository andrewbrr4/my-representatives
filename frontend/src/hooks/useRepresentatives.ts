import { useState, useCallback, useRef } from "react";
import type { Representative, ResearchSummary } from "@/types";

export function useRepresentatives() {
  const [representatives, setRepresentatives] = useState<Representative[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const lookup = useCallback(async (address: string) => {
    // Abort any in-flight request
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);
    setRepresentatives([]);

    try {
      const resp = await fetch("http://localhost:8000/api/representatives", {
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

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        // Keep the last potentially incomplete line in the buffer
        buffer = lines.pop() || "";

        let currentEvent = "";
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
        let currentEvent = "";
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
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }

    function handleSSEEvent(event: string, data: string) {
      if (event === "representatives") {
        const parsed = JSON.parse(data);
        // Mark all summaries as undefined (pending), not null (failed)
        setRepresentatives(
          parsed.representatives.map((r: Representative) => ({ ...r, summary: undefined }))
        );
      } else if (event === "research") {
        const { index, summary } = JSON.parse(data) as {
          index: number;
          summary: ResearchSummary | null;
        };
        setRepresentatives((prev) => {
          const updated = [...prev];
          updated[index] = { ...updated[index], summary };
          return updated;
        });
      } else if (event === "error") {
        const parsed = JSON.parse(data);
        setError(parsed.detail);
      }
    }
  }, []);

  return { representatives, loading, error, lookup };
}
