export type PartyBadge = { label: string; className: string };

export function getPartyBadge(party: string | null): PartyBadge | null {
  if (!party) return null;
  const p = party.trim().toLowerCase();
  if (p === "d" || p.startsWith("democrat")) {
    // Match the input form so the badge doesn't say "Democrat" while the
    // CardDescription says "· Democratic" on the same card.
    const label = p.startsWith("democratic") ? "Democratic" : "Democrat";
    return {
      label,
      className: "bg-party-democrat text-primary-foreground hover:bg-party-democrat/90",
    };
  }
  if (p === "r" || p.startsWith("republican")) {
    return {
      label: "Republican",
      className: "bg-party-republican text-primary-foreground hover:bg-party-republican/90",
    };
  }
  if (p === "i" || p.startsWith("independent")) {
    return {
      label: "Independent",
      className: "bg-party-independent text-primary-foreground hover:bg-party-independent/90",
    };
  }
  return null;
}
