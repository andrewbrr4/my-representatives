import type { Representative } from "@/types";

/**
 * Returns a numeric rank for a rep's office string. Lower = more senior.
 * Matching is case-insensitive and uses substring/word checks against the
 * raw `office` text returned by Cicero / the US Congress API.
 *
 * Within a level, ties break alphabetically by last name in `sortBySeniority`.
 */
export function getSeniorityRank(office: string, level: string): number {
  const o = office.toLowerCase();

  if (level === "federal") {
    if (o === "president") return 0;
    if (o.includes("vice president")) return 1;
    // "U.S. Senator", "United States Senator", etc. — but NOT "State Senator"
    if (o.includes("senator") && !o.includes("state")) return 2;
    if (
      (o.includes("representative") || o.includes("congressman") ||
        o.includes("congresswoman") || o.includes("house")) &&
      !o.includes("state")
    ) {
      return 3;
    }
    return 99;
  }

  if (level === "state") {
    if (o.includes("governor") && !o.includes("lieutenant")) return 0;
    if (o.includes("lieutenant governor")) return 1;
    if (o.includes("attorney general")) return 2;
    if (o.includes("secretary of state")) return 3;
    if (
      o.includes("treasurer") || o.includes("comptroller") ||
      o.includes("auditor")
    ) {
      return 4;
    }
    if (o.includes("state senator") || o.includes("state senate")) return 6;
    if (
      o.includes("state representative") || o.includes("state assembly") ||
      o.includes("assembly member") || o.includes("assemblyman") ||
      o.includes("assemblywoman") || o.includes("delegate") ||
      o.includes("state house")
    ) {
      return 7;
    }
    // Other statewide elected (Insurance Commissioner, etc.)
    return 5;
  }

  if (level === "municipal") {
    // Rank order: Mayor (0) → Other citywide (1, fallthrough) → Council (2) → School Board (3).
    // The fallthrough at the bottom returns 1 — between Mayor and Council.
    if (o.includes("mayor")) return 0;
    if (
      o.includes("council") || o.includes("alderman") ||
      o.includes("alderwoman") || o.includes("supervisor") ||
      o.includes("commissioner")
    ) {
      return 2;
    }
    if (
      o.includes("school board") || o.includes("soil") ||
      o.includes("water")
    ) {
      return 3;
    }
    // Other citywide (City Attorney, City Clerk, City Comptroller) — rank 1
    return 1;
  }

  return 99;
}

function lastName(name: string): string {
  const parts = name.trim().split(/\s+/);
  return (parts[parts.length - 1] || "").toLowerCase();
}

/**
 * Sorts a list of reps in-place-equivalent (returns a new sorted array)
 * by seniority rank, then by last name as a stable tiebreaker.
 */
export function sortBySeniority(reps: Representative[]): Representative[] {
  return [...reps].sort((a, b) => {
    const ra = getSeniorityRank(a.office, a.level);
    const rb = getSeniorityRank(b.office, b.level);
    if (ra !== rb) return ra - rb;
    return lastName(a.name).localeCompare(lastName(b.name));
  });
}
