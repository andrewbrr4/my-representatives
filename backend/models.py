from pydantic import BaseModel, Field


class AddressRequest(BaseModel):
    address: str


class Contact(BaseModel):
    website: str | None = None
    phone: str | None = None
    email: str | None = None


class Citation(BaseModel):
    title: str
    url: str


class ResearchFinding(BaseModel):
    fact: str
    source_url: str
    source_title: str


class RawResearch(BaseModel):
    findings: list[ResearchFinding]


class ResearchSummary(BaseModel):
    background: str = Field(description="Career history, how they came into office, relevant personal context. Paragraph form, no bullets. Embed inline citation markers like [1], [2] referencing the citations list. Max 3-5 sentences.")
    policy_positions: str = Field(description="Where they stand on key issues based on voting record and public statements, not campaign messaging. Paragraph form, no bullets. Embed inline citation markers like [1], [2] referencing the citations list. Max 3-5 sentences.")
    recent_legislative_record: list[str] = Field(description="Key legislative measures they recently supported or opposed. Each item is one measure. Embed inline citation markers like [1], [2] referencing the citations list. Max 3-5 items.")
    recent_press: list[str] = Field(description="Recent press coverage, public statements, local news. Each item is one story or event. Embed inline citation markers like [1], [2] referencing the citations list. Max 3-5 items.")
    top_donors: list[str] = Field(description="Largest political donors, five max. Each item is one donor. Embed inline citation markers like [1], [2] referencing the citations list. Max 3-5 items.")
    citations: list[Citation] = Field(description="Ordered list of sources referenced in the text. citations[0] corresponds to [1], citations[1] to [2], etc. Must include every source referenced by inline markers. No cap on list length.")


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
