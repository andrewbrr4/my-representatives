import { useQuery } from "@tanstack/react-query";
import type { Representative, RepresentativesResponse } from "@/types";

const API_URL = import.meta.env.VITE_API_URL;
const STALE_TIME = 5 * 60 * 1000; // 5 minutes

async function fetchRepresentatives(address: string): Promise<Representative[]> {
  const resp = await fetch(`${API_URL}/api/representatives`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ address }),
  });

  if (!resp.ok) {
    const data = await resp.json().catch(() => null);
    throw new Error(data?.detail || `Request failed (${resp.status})`);
  }

  const { representatives }: RepresentativesResponse = await resp.json();
  return representatives;
}

export function useRepresentativesQuery(address: string | null) {
  return useQuery({
    queryKey: ["representatives", address],
    queryFn: () => fetchRepresentatives(address!),
    enabled: !!address,
    staleTime: STALE_TIME,
  });
}
