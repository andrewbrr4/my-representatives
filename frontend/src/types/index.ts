// These mirror the Pydantic models on the backend

export interface Contact {
  website: string | null;
  phone: string | null;
  email: string | null;
}

export interface ResearchSummary {
  background: string;
  recent_news: string;
  policy_positions: string;
  committees: string;
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
