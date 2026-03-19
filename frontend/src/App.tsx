import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { AddressSearch } from "@/components/AddressSearch";
import { RepCard } from "@/components/RepCard";
import { SkeletonCard } from "@/components/SkeletonCard";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useRepresentatives } from "@/hooks/useRepresentatives";
import { useResearch } from "@/hooks/useResearch";
import type { Representative } from "@/types";

// Group reps by level for display
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

function App() {
  const { representatives, loading, error, lookup } = useRepresentatives();
  const { requestResearch, getStatus, getSummary } = useResearch();
  const [searchedAddress, setSearchedAddress] = useState<string | null>(null);

  function handleSearch(address: string) {
    setSearchedAddress(address);
    lookup(address);
  }

  function handleReset() {
    setSearchedAddress(null);
  }

  const hasResults = representatives.length > 0;
  const groups = groupByLevel(representatives);

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-6 py-12">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold tracking-tight mb-2">MyReps</h1>
          <p className="text-muted-foreground">
            Find your elected representatives at every level of government.
          </p>
        </div>

        {/* Welcome message (before search) */}
        {!searchedAddress && !loading && (
          <div className="max-w-2xl mx-auto mb-8 text-center space-y-4">
            <p className="text-lg text-muted-foreground">
              You deserve to know who represents you — and what they're doing.
            </p>
            <p className="text-sm text-muted-foreground">
              Most of us only think about our elected officials at election time, and even then we focus on the big races. But the representatives who affect your daily life the most — your state legislators, your city council members — are often the ones you hear about the least.
            </p>
            <p className="text-sm text-muted-foreground">
              MyReps changes that. Enter your address and get every elected official who represents you, from the President to your city council, with up-to-date summaries of what they've been working on and direct contact info so you can reach them.
            </p>
            <p className="text-sm font-semibold text-foreground">
              Know who represents you. Hold them accountable. Make your voice heard.
            </p>
          </div>
        )}

        {/* Search or address display */}
        <div className="flex justify-center mb-8">
          {searchedAddress && (!loading || representatives.length > 0) ? (
            <div className="flex items-center gap-3 text-sm">
              <span className="text-muted-foreground">
                Results for: <strong className="text-foreground">{searchedAddress}</strong>
              </span>
              <button
                onClick={handleReset}
                className="text-primary underline underline-offset-2 hover:text-primary/80"
              >
                New search
              </button>
            </div>
          ) : (
            <AddressSearch onSearch={handleSearch} loading={loading} />
          )}
        </div>

        {/* Loading state (before any reps arrive) */}
        {loading && !hasResults && (
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

        {/* Error state */}
        {error && (
          <div className="text-center p-6 rounded-lg bg-destructive/10 text-destructive">
            {error}
          </div>
        )}

        {/* Results */}
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
      </div>
    </div>
  );
}

export default App;
