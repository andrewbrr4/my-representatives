import { useState } from "react";
import { Search } from "lucide-react";
import type { Representative, Citation } from "@/types";
import { useIssueSearch } from "@/hooks/useIssueSearch";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { renderInline } from "@/components/RepCard";

function IssueResult({
  label,
  items,
  citations,
  loading,
}: {
  label: string;
  items: string[] | null;
  citations: Citation[];
  loading: boolean;
}) {
  return (
    <div className="mt-2 p-3 rounded-lg bg-muted/30 border">
      <h4 className="font-semibold text-sm text-foreground mb-1">{label}</h4>
      {loading && !items ? (
        <div className="space-y-1.5">
          <Skeleton className="h-3.5 w-full" />
          <Skeleton className="h-3.5 w-5/6" />
        </div>
      ) : items ? (
        <ul className="list-disc pl-5 space-y-1 text-sm leading-relaxed">
          {items.map((item, i) => (
            <li key={i}>{renderInline(item, citations)}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

interface IssueSearchProps {
  rep: Representative;
}

export function IssueSearch({ rep }: IssueSearchProps) {
  const { searchIssue, getIssueEntries } = useIssueSearch(rep);
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const issueEntries = getIssueEntries();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || searching) return;

    setError(null);
    setSearching(true);
    const errMsg = await searchIssue(trimmed);
    if (errMsg) setError(errMsg);
    setSearching(false);
    setQuery("");
  };

  return (
    <div>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Look up a specific issue (e.g. immigration, housing)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-9"
            disabled={searching}
          />
        </div>
        <Button type="submit" variant="outline" size="sm" disabled={searching || !query.trim()}>
          {searching ? "Searching…" : "Search"}
        </Button>
      </form>

      {error && (
        <p className="text-sm text-muted-foreground mt-2">{error}</p>
      )}

      {issueEntries.map(({ key, entry }) => (
        <IssueResult
          key={key}
          label={entry.issue?.label ?? "Issue"}
          items={entry.summary?.stance_summary ?? null}
          citations={entry.summary?.citations ?? []}
          loading={entry.status === "loading"}
        />
      ))}
    </div>
  );
}
