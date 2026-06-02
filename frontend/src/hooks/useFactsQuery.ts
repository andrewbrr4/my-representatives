import { useQuery } from "@tanstack/react-query";

const API_URL = import.meta.env.VITE_API_URL;

/**
 * Fetches the loading-carousel facts. With an `issueId`, fetches facts themed
 * to that issue (falling back server-side to general facts if none exist);
 * without one, fetches the general civics facts. Cached per issue for the
 * session (facts don't change while the app is open).
 */
export function useFactsQuery(issueId?: string) {
  return useQuery({
    queryKey: ["facts", issueId ?? "general"],
    queryFn: async (): Promise<string[]> => {
      const url = issueId
        ? `${API_URL}/api/facts?issue=${encodeURIComponent(issueId)}`
        : `${API_URL}/api/facts`;
      const resp = await fetch(url);
      if (!resp.ok) return [];
      const data = await resp.json();
      return (data.facts as string[]) ?? [];
    },
    staleTime: Infinity,
  });
}
