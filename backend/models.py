from pydantic import BaseModel, Field


class AddressRequest(BaseModel):
    address: str


class Contact(BaseModel):
    website: str | None = None
    phone: str | None = None
    email: str | None = None


class ResearchSummary(BaseModel):
    background: str = Field(description="Career history, how they came into office, relevant personal context. Paragraph form, no bullets.")
    policy_positions: str = Field(description="Where they stand on key issues based on voting record and public statements, not campaign messaging. Paragraph form, no bullets.")
    recent_legislative_record: list[str] = Field(description="Key legislative measures they recently supported or opposed. Each item is one measure.")
    recent_press: list[str] = Field(description="Recent press coverage, public statements, local news. Each item is one story or event.")
    top_donors: list[str] = Field(description="Largest political donors, five max. Each item is one donor.")


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
