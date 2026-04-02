// These mirror the Pydantic models on the backend

export interface Contact {
  website: string | null;
  phone: string | null;
  email: string | null;
}

export interface Citation {
  title: string;
  url: string;
}

export interface ResearchSummary {
  policy_positions: string[] | null;
  policy_positions_citations: Citation[];
  recent_legislative_record: string[] | null;
  recent_legislative_record_citations: Citation[];
  accomplishments: string[] | null;
  accomplishments_citations: Citation[];
  controversies: string[] | null;
  controversies_citations: Citation[];
  top_donors: string[] | null;
  top_donors_citations: Citation[];
}

export interface Representative {
  name: string;
  office: string;
  level: "federal" | "state" | "municipal";
  party: string | null;
  photo_url: string | null;
  contact: Contact;
}

export interface RepresentativesResponse {
  representatives: Representative[];
}

export interface ResearchResponse {
  research_id: string;
  status: "pending" | "in_progress" | "complete" | "failed";
  summary: ResearchSummary | null;
}

export interface PollingLocation {
  name: string;
  address: string;
  hours: string | null;
}

export interface VoterInfo {
  registration_url: string | null;
  absentee_url: string | null;
  ballot_info_url: string | null;
  polling_location_url: string | null;
  early_vote_sites: PollingLocation[];
  drop_off_locations: PollingLocation[];
  mail_only: boolean;
  admin_body_name: string | null;
  admin_body_url: string | null;
}

export interface Candidate {
  name: string;
  office: string;
  level: "federal" | "state" | "municipal";
  party: string | null;
  photo_url: string | null;
  contest_name: string;
  incumbent: boolean;
}

export interface Contest {
  office: string;
  level: "federal" | "state" | "municipal";
  district_name: string | null;
  candidates: Candidate[];
}

export interface Election {
  name: string;
  date: string;
  election_type: string;
  polling_location: PollingLocation | null;
  voter_info: VoterInfo | null;
  contests: Contest[];
}

export interface ElectionsResponse {
  elections: Election[];
  research_ids: Record<string, string>;
}

// --- Issue research types ---

export interface IssueInfo {
  id: string;
  label: string;
}

export interface IssueMatchResponse {
  matched: boolean;
  issue: IssueInfo | null;
  novel: boolean;
  message: string | null;
}

export interface IssueStanceSummary {
  stance_summary: string[] | null;
  citations: Citation[];
}

export interface IssueResearchResponse {
  research_id: string;
  status: "pending" | "in_progress" | "complete" | "failed";
  summary: IssueStanceSummary | null;
}

// --- Election types ---

export interface ElectionResearchSummary {
  election_context: string | null;
  key_issues_and_significance: string[] | null;
  citations: Citation[];
}

export interface ElectionResearchResponse {
  research_id: string;
  status: "pending" | "in_progress" | "complete" | "failed";
  summary: ElectionResearchSummary | null;
}
