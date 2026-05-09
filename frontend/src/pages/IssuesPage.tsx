import { useMemo } from "react";
import { Search } from "lucide-react";
import { useAddress } from "@/contexts/AddressContext";
import { useRepresentativesQuery } from "@/hooks/useRepresentativesQuery";
import { useIssues } from "@/contexts/IssuesContext";
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
  const { data, isLoading: repsLoading } = useRepresentativesQuery(address);
  const representatives = data?.representatives ?? [];

  const {
    query,
    setQuery,
    selected,
    toggleRep,
    lastQuery,
    compareStatus,
    matchedIssue,
    errorMessage,
    getResult,
    retryRep,
    comparedReps,
    handleSubmit,
  } = useIssues();

  const groups = useMemo(() => groupByLevel(representatives), [representatives]);

  const selectedReps = useMemo(
    () => representatives.filter((r) => selected.has(repId(r))),
    [representatives, selected],
  );

  const canSubmit =
    query.trim().length > 0 &&
    selectedReps.length > 0 &&
    compareStatus !== "matching";

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit || selectedReps.length === 0) return;
    await handleSubmit(selectedReps);
  };

  const showResults = compareStatus !== "idle" && compareStatus !== "matching" && matchedIssue;

  return (
    <>
      <div className="max-w-4xl mx-auto space-y-6">
        <form onSubmit={onSubmit} className="space-y-4">
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
              {comparedReps.map((rep) => (
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
