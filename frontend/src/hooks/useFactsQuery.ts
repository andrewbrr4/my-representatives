import { useQuery } from "@tanstack/react-query";

const API_URL = import.meta.env.VITE_API_URL;

/**
 * Fetches the civics/America fun facts shown in the loading carousel.
 * Cached for the whole session (facts don't change while the app is open).
 */
export function useFactsQuery() {
  return useQuery({
    queryKey: ["facts"],
    queryFn: async (): Promise<string[]> => {
      const resp = await fetch(`${API_URL}/api/facts`);
      if (!resp.ok) return [];
      const data = await resp.json();
      return (data.facts as string[]) ?? [];
    },
    staleTime: Infinity,
  });
}
