import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// Props are like function arguments — this component receives an `onSearch` callback
// and a `loading` boolean from its parent.
interface AddressSearchProps {
  onSearch: (address: string) => void;
  loading: boolean;
}

export function AddressSearch({ onSearch, loading }: AddressSearchProps) {
  const [address, setAddress] = useState("");

  function handleSubmit(e: React.FormEvent) {
    // Prevent the browser from reloading the page (default form behavior)
    e.preventDefault();
    if (address.trim()) {
      onSearch(address.trim());
    }
  }

  // JSX below — looks like HTML but it's JavaScript. `className` = HTML's `class`.
  // The Tailwind classes: flex = flexbox, gap-3 = spacing, w-full = full width, etc.
  return (
    <form onSubmit={handleSubmit} className="flex gap-3 w-full max-w-xl">
      <Input
        type="text"
        placeholder="Enter your address (e.g. 123 Main St, Austin, TX 78701)"
        value={address}
        onChange={(e) => setAddress(e.target.value)}
        className="flex-1"
        disabled={loading}
      />
      <Button type="submit" disabled={loading || !address.trim()}>
        {loading ? "Searching…" : "Search"}
      </Button>
    </form>
  );
}
