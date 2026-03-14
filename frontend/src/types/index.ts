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
  background: string;
  background_citations: Citation[];
  policy_positions: string;
  policy_positions_citations: Citation[];
  recent_legislative_record: string[];
  recent_legislative_record_citations: Citation[];
  accomplishments: string[];
  accomplishments_citations: Citation[];
  controversies: string[];
  controversies_citations: Citation[];
  recent_press: string[];
  recent_press_citations: Citation[];
  top_donors: string[];
  top_donors_citations: Citation[];
}

export interface Representative {
  name: string;
  office: string;
  level: "federal" | "state" | "municipal";
  party: string | null;
  photo_url: string | null;
  contact: Contact;
  summary: ResearchSummary | null | undefined; // undefined=pending, null=failed
}

export interface RepresentativesResponse {
  representatives: Representative[];
}

export interface JobResearchEntry {
  index: number;
  status: "pending" | "complete" | "failed";
  summary: ResearchSummary | null;
}

export interface JobStatusResponse {
  job_id: string;
  status: "lookup" | "researching" | "done" | "error";
  representatives: Representative[] | null;
  research: JobResearchEntry[] | null;
  error_detail: string | null;
}
