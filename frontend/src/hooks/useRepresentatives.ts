import { useState } from "react";
import type { Representative } from "@/types";

// This is a "custom hook" — a reusable function that manages state and logic.
// Think of it like a service class in Python, but for UI state.

export function useRepresentatives() {
  // useState is how React tracks values that, when changed, re-render the UI.
  // It returns [currentValue, setterFunction].
  const [representatives, setRepresentatives] = useState<Representative[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function lookup(address: string) {
    setLoading(true);
    setError(null);
    setRepresentatives([]);

    try {
      const resp = await fetch("http://localhost:8000/api/representatives", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address }),
      });

      if (!resp.ok) {
        const data = await resp.json().catch(() => null);
        throw new Error(data?.detail || `Request failed (${resp.status})`);
      }

      const data = await resp.json();
      setRepresentatives(data.representatives);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return { representatives, loading, error, lookup };
}
