import { useState, useCallback, useRef, useEffect } from "react";
import type { Representative, RepresentativesResponse } from "@/types";

const API_URL = import.meta.env.VITE_API_URL;

export function useRepresentatives() {
  const [representatives, setRepresentatives] = useState<Representative[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const lookup = useCallback(async (address: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);
    setRepresentatives([]);

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

      const { representatives }: RepresentativesResponse = await resp.json();
      setRepresentatives(representatives);
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }, []);

  return { representatives, loading, error, lookup };
}
