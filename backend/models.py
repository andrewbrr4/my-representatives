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
    recent_legislative_record: str = Field(description="Key legislative measures they recently supported or opposed. Bulleted markdown list.")
    recent_press: str = Field(description="Recent press coverage, public statements, local news. Bulleted markdown list.")
    top_donors: str = Field(description="Largest political donors, five max. Bulleted markdown list.")


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
