import { useState, useCallback, useRef, useEffect } from "react";
import type { Election, ElectionsResponse } from "@/types";

const API_URL = import.meta.env.VITE_API_URL;

export function useElections() {
  const [elections, setElections] = useState<Election[]>([]);
  const [researchIds, setResearchIds] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fetchedAddress = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const fetchElections = useCallback(async (address: string) => {
    // Deduplicate: don't re-fetch for same address
    if (fetchedAddress.current === address && elections.length > 0) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    try {
      const resp = await fetch(`${API_URL}/api/elections`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address }),
        signal: controller.signal,
      });

      if (!resp.ok) {
        const data = await resp.json().catch(() => null);
        throw new Error(data?.detail || `Request failed (${resp.status})`);
      }

      const data: ElectionsResponse = await resp.json();
      setElections(data.elections);
      setResearchIds(data.research_ids);
      fetchedAddress.current = address;
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }, [elections.length]);

  return { elections, researchIds, loading, error, fetchElections };
}
