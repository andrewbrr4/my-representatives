from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AddressRequest(BaseModel):
    address: str


class Contact(BaseModel):
    website: str | None = None
    phone: str | None = None
    email: str | None = None


class Citation(BaseModel):
    title: str
    url: str


class SectionResult(BaseModel):
    content: str
    citations: list[Citation]


class ListSectionResult(BaseModel):
    items: list[str]
    citations: list[Citation]


class ResearchSummary(BaseModel):
    background: str = Field(description="Career history, how they came into office, relevant personal context. Paragraph form, no bullets. Embed inline citation markers like [1], [2] referencing the background_citations list. Max 1-2 sentences.")
    background_citations: list[Citation] = Field(default_factory=list, description="Ordered list of sources for background section.")
    policy_positions: str = Field(description="Where they stand on key issues based on voting record and public statements, not campaign messaging. Paragraph form, no bullets. Embed inline citation markers like [1], [2] referencing the policy_positions_citations list. Max 3-5 sentences.")
    policy_positions_citations: list[Citation] = Field(default_factory=list, description="Ordered list of sources for policy_positions section.")
    recent_legislative_record: list[str] = Field(description="Key legislative measures they recently supported or opposed. Each item is one measure. Embed inline citation markers like [1], [2] referencing the recent_legislative_record_citations list. Max 3-5 items.")
    recent_legislative_record_citations: list[Citation] = Field(default_factory=list, description="Ordered list of sources for recent_legislative_record section.")
    accomplishments: list[str] = Field(description="Notable achievements, successful initiatives, awards. Each item is one accomplishment. Embed inline citation markers like [1], [2] referencing the accomplishments_citations list. Max 3-5 items.")
    accomplishments_citations: list[Citation] = Field(default_factory=list, description="Ordered list of sources for accomplishments section.")
    controversies: list[str] = Field(description="Scandals, ethics complaints, controversial actions or statements. Each item is one controversy. Embed inline citation markers like [1], [2] referencing the controversies_citations list. Max 3-5 items.")
    controversies_citations: list[Citation] = Field(default_factory=list, description="Ordered list of sources for controversies section.")
    recent_press: list[str] = Field(description="Recent press coverage, public statements, local news. Each item is one story or event. Embed inline citation markers like [1], [2] referencing the recent_press_citations list. Max 3-5 items.")
    recent_press_citations: list[Citation] = Field(default_factory=list, description="Ordered list of sources for recent_press section.")
    top_donors: list[str] = Field(description="Largest political donors, five max. Each item is one donor. Embed inline citation markers like [1], [2] referencing the top_donors_citations list. Max 3-5 items.")
    top_donors_citations: list[Citation] = Field(default_factory=list, description="Ordered list of sources for top_donors section.")

    _NOT_FOUND = "Information not found."

    @model_validator(mode="after")
    def fill_missing_fields(self) -> "ResearchSummary":
        fallback = self._NOT_FOUND
        for field_name, field_info in self.model_fields.items():
            if field_name.endswith("_citations"):
                continue
            value = getattr(self, field_name)
            if isinstance(value, str) and not value.strip():
                object.__setattr__(self, field_name, fallback)
            elif isinstance(value, list) and len(value) == 0:
                object.__setattr__(self, field_name, [fallback])
        return self


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


class LookupResponse(BaseModel):
    job_id: str
    representatives: list[Representative]


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["lookup", "researching", "done", "error"]
    representatives: list[Representative] | None = None
    research: list[dict] | None = None
    error_detail: str | None = None


class TransactionCreate(BaseModel):
    type: Literal["inflow", "outflow"]
    source: str
    billing_model: Literal["per_request", "bulk", "subscription"]
    amount_usd: float
    description: str | None = None
    job_id: str | None = None


class TransactionOut(BaseModel):
    id: int
    type: str
    source: str
    billing_model: str
    amount_usd: Decimal
    description: str | None
    job_id: str | None
    created_at: datetime
    balance_after: Decimal | None
