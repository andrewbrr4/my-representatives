import { useState } from "react";
import { AddressSearch } from "@/components/AddressSearch";
import { RepCard } from "@/components/RepCard";
import { SkeletonCard } from "@/components/SkeletonCard";
import { useRepresentatives } from "@/hooks/useRepresentatives";
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
      <div className="max-w-4xl mx-auto px-4 py-12">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold tracking-tight mb-2">MyReps</h1>
          <p className="text-muted-foreground">
            Find your elected representatives at every level of government.
          </p>
        </div>

        {/* Search or address display */}
        <div className="flex justify-center mb-8">
          {searchedAddress && !loading ? (
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

        {/* Loading state */}
        {loading && (
          <div className="space-y-4">
            <p className="text-center text-sm text-muted-foreground">
              Researching your representatives… This may take up to 30 seconds.
            </p>
            <div className="grid gap-4 md:grid-cols-2">
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
        {hasResults && !loading && (
          <div className="space-y-8">
            {groups.map((group) => (
              <section key={group.level}>
                <h2 className="text-xl font-semibold mb-4 border-b pb-2">
                  {group.label}
                </h2>
                <div className="grid gap-4 md:grid-cols-2">
                  {group.reps.map((rep) => (
                    <RepCard key={`${rep.name}-${rep.office}`} rep={rep} />
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
