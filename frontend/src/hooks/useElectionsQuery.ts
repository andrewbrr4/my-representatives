import { useQuery } from "@tanstack/react-query";
import type { Election, ElectionsResponse } from "@/types";

const API_URL = import.meta.env.VITE_API_URL;
const STALE_TIME = 5 * 60 * 1000; // 5 minutes

interface ElectionsResult {
  elections: Election[];
  researchIds: Record<string, string>;
}

async function fetchElections(address: string): Promise<ElectionsResult> {
  const resp = await fetch(`${API_URL}/api/elections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ address }),
  });

  if (!resp.ok) {
    const data = await resp.json().catch(() => null);
    throw new Error(data?.detail || `Request failed (${resp.status})`);
  }

  const data: ElectionsResponse = await resp.json();
  return { elections: data.elections, researchIds: data.research_ids };
}

export function useElectionsQuery(address: string | null) {
  return useQuery({
    queryKey: ["elections", address],
    queryFn: () => fetchElections(address!),
    enabled: !!address,
    staleTime: STALE_TIME,
  });
}
