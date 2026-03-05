// These mirror the Pydantic models on the backend

export interface Contact {
  website: string | null;
  phone: string | null;
  email: string | null;
}

export interface Representative {
  name: string;
  office: string;
  level: "federal" | "state" | "municipal";
  party: string | null;
  photo_url: string | null;
  contact: Contact;
  summary: string | null;
}

export interface RepresentativesResponse {
  representatives: Representative[];
}
