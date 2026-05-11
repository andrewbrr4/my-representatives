import { AddressSearch } from "@/components/AddressSearch";
import { useAddress } from "@/contexts/AddressContext";

export function SearchPage() {
  const { setAddress } = useAddress();

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-6 py-12">
        <div className="text-center mb-8">
          <h1 className="text-6xl font-bold tracking-tight mb-3">KnowMyReps</h1>
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Your elected officials, at every level
          </p>
        </div>

        <div className="max-w-2xl mx-auto mb-8 text-center space-y-4">
          <p className="text-xl font-semibold text-foreground leading-snug">
            You deserve to know who represents you — and what they're doing.
          </p>
          <p className="text-base text-muted-foreground leading-relaxed">
            Most of us only think about our elected officials at election time, and even then we focus on the big races. But the representatives who affect your daily life the most — your state legislators, your city council members — are often the ones you hear about the least.
          </p>
          <p className="text-base text-muted-foreground leading-relaxed">
            KnowMyReps changes that. Enter your address and get every elected official who represents you, from the President to your city council, with up-to-date summaries of what they've been working on and direct contact info so you can reach them.
          </p>
          <p className="text-sm font-bold uppercase tracking-wider text-foreground">
            Know who represents you. Hold them accountable. Make your voice heard.
          </p>
        </div>

        <div className="flex justify-center mb-8">
          <AddressSearch onSearch={setAddress} loading={false} />
        </div>
      </div>
    </div>
  );
}
