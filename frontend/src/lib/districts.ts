import type { DistrictInfo } from "@/types";

const STATE_NAMES: Record<string, string> = {
  AL: "Alabama", AK: "Alaska", AZ: "Arizona", AR: "Arkansas", CA: "California",
  CO: "Colorado", CT: "Connecticut", DE: "Delaware", FL: "Florida", GA: "Georgia",
  HI: "Hawaii", ID: "Idaho", IL: "Illinois", IN: "Indiana", IA: "Iowa",
  KS: "Kansas", KY: "Kentucky", LA: "Louisiana", ME: "Maine", MD: "Maryland",
  MA: "Massachusetts", MI: "Michigan", MN: "Minnesota", MS: "Mississippi", MO: "Missouri",
  MT: "Montana", NE: "Nebraska", NV: "Nevada", NH: "New Hampshire", NJ: "New Jersey",
  NM: "New Mexico", NY: "New York", NC: "North Carolina", ND: "North Dakota", OH: "Ohio",
  OK: "Oklahoma", OR: "Oregon", PA: "Pennsylvania", RI: "Rhode Island", SC: "South Carolina",
  SD: "South Dakota", TN: "Tennessee", TX: "Texas", UT: "Utah", VT: "Vermont",
  VA: "Virginia", WA: "Washington", WV: "West Virginia", WI: "Wisconsin", WY: "Wyoming",
  DC: "District of Columbia",
};

// Override "State House" for states that name their lower chamber differently.
const LOWER_CHAMBER_NAMES: Record<string, string> = {
  CA: "Assembly",
  NV: "Assembly",
  NJ: "General Assembly",
  NY: "Assembly",
  WI: "State Assembly",
  MD: "House of Delegates",
  VA: "House of Delegates",
  WV: "House of Delegates",
};

function ordinal(n: number): string {
  const v = n % 100;
  if (v >= 11 && v <= 13) return `${n}th`;
  const suffixes: Record<number, string> = { 1: "st", 2: "nd", 3: "rd" };
  return `${n}${suffixes[n % 10] ?? "th"}`;
}

export interface DistrictBreakdown {
  federal: string | null;
  state: string | null;
  municipal: string | null;
}

export function formatDistrictBreakdown(info: DistrictInfo): DistrictBreakdown {
  const stateFull = info.state ? STATE_NAMES[info.state] ?? info.state : null;
  const lowerChamber = (info.state && LOWER_CHAMBER_NAMES[info.state]) || "State House";

  let federal: string | null = null;
  if (stateFull && info.congressional_district) {
    const n = parseInt(info.congressional_district, 10);
    const cd = Number.isFinite(n) ? ordinal(n) : info.congressional_district;
    federal = `${stateFull}'s ${cd} congressional district`;
  }

  const stateParts: string[] = [];
  if (info.state_senate_district) {
    stateParts.push(`State Senate district ${info.state_senate_district}`);
  }
  if (info.state_house_district) {
    stateParts.push(`${lowerChamber} district ${info.state_house_district}`);
  }
  const state = stateParts.length ? stateParts.join(" and ") : null;

  const municipal = info.municipality ?? null;

  return { federal, state, municipal };
}
