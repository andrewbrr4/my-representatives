import { ChevronDown, ChevronRight } from "lucide-react";
import { RepCard } from "@/components/RepCard";
import { SkeletonCard } from "@/components/SkeletonCard";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useRepresentativesQuery } from "@/hooks/useRepresentativesQuery";
import { useResearch } from "@/hooks/useResearch";
import { useAddress } from "@/contexts/AddressContext";
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

export function RepresentativesPage() {
  const { address } = useAddress();
  const { data: representatives = [], isLoading, error } = useRepresentativesQuery(address);
  const { requestResearch, getStatus, getSummary } = useResearch();

  const hasResults = representatives.length > 0;
  const groups = groupByLevel(representatives);

  return (
    <>
      {isLoading && !hasResults && (
        <div className="space-y-4">
          <p className="text-center text-sm text-muted-foreground">
            Looking up your representatives…
          </p>
          <div className="grid gap-4 grid-cols-1 max-w-4xl mx-auto">
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="text-center p-6 rounded-lg bg-destructive/10 text-destructive">
          {error.message}
        </div>
      )}

      {hasResults && (
        <div className="space-y-8">
          {groups.map((group) => (
            <Collapsible key={group.level} defaultOpen asChild>
              <section className="max-w-4xl mx-auto">
                <CollapsibleTrigger className="flex w-full items-center gap-2 border-b pb-2 cursor-pointer group">
                  <span className="text-muted-foreground transition-transform group-data-[state=closed]:rotate-0 group-data-[state=open]:rotate-0">
                    <ChevronRight className="h-5 w-5 group-data-[state=open]:hidden" />
                    <ChevronDown className="h-5 w-5 group-data-[state=closed]:hidden" />
                  </span>
                  <h2 className="text-xl font-semibold">
                    {group.label}
                  </h2>
                  <span className="text-sm text-muted-foreground">
                    ({group.reps.length})
                  </span>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <div className="grid gap-4 grid-cols-1 mt-4">
                    {group.reps.map((rep) => (
                      <RepCard
                        key={`${rep.name}-${rep.office}`}
                        rep={rep}
                        researchStatus={getStatus(rep)}
                        summary={getSummary(rep)}
                        onResearch={() => requestResearch(rep)}
                      />
                    ))}
                  </div>
                </CollapsibleContent>
              </section>
            </Collapsible>
          ))}
        </div>
      )}
    </>
  );
}
