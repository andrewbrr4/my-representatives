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
  background: string | null;
  background_citations: Citation[];
  policy_positions: string | null;
  policy_positions_citations: Citation[];
  recent_legislative_record: string[] | null;
  recent_legislative_record_citations: Citation[];
  accomplishments: string[] | null;
  accomplishments_citations: Citation[];
  controversies: string[] | null;
  controversies_citations: Citation[];
  recent_press: string[] | null;
  recent_press_citations: Citation[];
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
