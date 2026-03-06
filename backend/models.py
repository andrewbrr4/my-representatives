from pydantic import BaseModel


class AddressRequest(BaseModel):
    address: str


class Contact(BaseModel):
    website: str | None = None
    phone: str | None = None
    email: str | None = None


class ResearchSummary(BaseModel):
    background: str
    recent_news: str
    policy_positions: str
    committees: str


class Representative(BaseModel):
    name: str
    office: str
    level: str
    party: str | None = None
    photo_url: str | None = None
    contact: Contact = Contact()
    summary: ResearchSummary | None = None


class RepresentativesResponse(BaseModel):
    representatives: list[Representative]
