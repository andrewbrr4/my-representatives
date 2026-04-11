import { useState, useMemo } from "react";
import { Search } from "lucide-react";
import { useAddress } from "@/contexts/AddressContext";
import { useRepresentativesQuery } from "@/hooks/useRepresentativesQuery";
import { useMultiIssueResearch } from "@/hooks/useMultiIssueResearch";
import { IssueCompareResult } from "@/components/IssueCompareResult";
import { SkeletonCard } from "@/components/SkeletonCard";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import type { Representative } from "@/types";

function groupByLevel(reps: Representative[]) {
  const groups: { label: string; level: string; reps: Representative[] }[] = [
    { label: "Federal", level: "federal", reps: [] },
    { label: "State", level: "state", reps: [] },
    { label: "Municipal", level: "municipal", reps: [] },
  ];
  for (const rep of reps) {
    const group = groups.find((g) => g.level === rep.level);
    if (group) group.reps.push(rep);
    else groups[2].reps.push(rep);
  }
  return groups.filter((g) => g.reps.length > 0);
}

function repId(rep: Representative): string {
  return `${rep.name}|${rep.office}`;
}

export function IssuesPage() {
  const { address } = useAddress();
  const { data: representatives = [], isLoading: repsLoading } = useRepresentativesQuery(address);

  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [lastQuery, setLastQuery] = useState("");

  const {
    compareStatus,
    matchedIssue,
    errorMessage,
    compareIssue,
    getResult,
    retryRep,
  } = useMultiIssueResearch();

  const groups = useMemo(() => groupByLevel(representatives), [representatives]);

  const selectedReps = useMemo(
    () => representatives.filter((r) => selected.has(repId(r))),
    [representatives, selected],
  );

  const toggleRep = (rep: Representative) => {
    setSelected((prev) => {
      const next = new Set(prev);
      const id = repId(rep);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const canSubmit =
    query.trim().length > 0 &&
    selected.size > 0 &&
    compareStatus !== "matching";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setLastQuery(query.trim());
    await compareIssue(query.trim(), selectedReps);
  };

  const showResults = compareStatus !== "idle" && compareStatus !== "matching" && matchedIssue;

  return (
    <>
      <div className="max-w-4xl mx-auto space-y-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Issue input */}
          <div>
            <label className="block text-sm font-medium mb-1.5">Issue</label>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Enter an issue (e.g. housing, immigration, gun control)"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="pl-9"
                disabled={compareStatus === "matching"}
              />
            </div>
          </div>

          {/* Rep selection */}
          <div>
            <label className="block text-sm font-medium mb-1.5">
              Select representatives to compare
            </label>

            {repsLoading && (
              <div className="space-y-2">
                <SkeletonCard />
              </div>
            )}

            {!repsLoading && representatives.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No representatives found for your address.
              </p>
            )}

            {groups.map((group) => (
              <div key={group.level} className="mb-3">
                <h3 className="text-sm font-semibold text-muted-foreground mb-1.5">
                  {group.label}
                </h3>
                <div className="space-y-1">
                  {group.reps.map((rep) => {
                    const id = repId(rep);
                    return (
                      <label
                        key={id}
                        className="flex items-center gap-2.5 py-1 px-2 rounded hover:bg-muted/50 cursor-pointer"
                      >
                        <Checkbox
                          checked={selected.has(id)}
                          onCheckedChange={() => toggleRep(rep)}
                          disabled={compareStatus === "matching"}
                        />
                        <span className="text-sm">
                          {rep.name}
                          <span className="text-muted-foreground">
                            {" "}&mdash; {rep.office}
                            {rep.party && ` · ${rep.party}`}
                          </span>
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          {/* Submit button */}
          <Button type="submit" disabled={!canSubmit} className="w-full">
            {compareStatus === "matching"
              ? "Matching issue..."
              : `Compare${selected.size > 0 ? ` (${selected.size} selected)` : ""}`}
          </Button>
        </form>

        {/* Error message */}
        {errorMessage && (
          <p className="text-sm text-muted-foreground">{errorMessage}</p>
        )}

        {/* Results area */}
        {showResults && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">
              {matchedIssue.label}
            </h2>
            <div className="space-y-3">
              {selectedReps.map((rep) => (
                <IssueCompareResult
                  key={repId(rep)}
                  rep={rep}
                  result={getResult(rep)}
                  onRetry={() => retryRep(rep, lastQuery)}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
