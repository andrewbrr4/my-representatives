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
  policy_positions: string;
  recent_legislative_record: string[];
  recent_press: string[];
  top_donors: string[];
  citations: Citation[];
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
