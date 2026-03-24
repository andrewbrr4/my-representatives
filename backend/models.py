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
    background: str | None = Field(default=None, description="Career history, how they came into office, relevant personal context. Paragraph form, no bullets. Embed inline citation markers like [1], [2] referencing the background_citations list. Max 1-2 sentences.")
    background_citations: list[Citation] = Field(default_factory=list, description="Ordered list of sources for background section.")
    policy_positions: str | None = Field(default=None, description="Where they stand on key issues based on voting record and public statements, not campaign messaging. Paragraph form, no bullets. Embed inline citation markers like [1], [2] referencing the policy_positions_citations list. Max 3-5 sentences.")
    policy_positions_citations: list[Citation] = Field(default_factory=list, description="Ordered list of sources for policy_positions section.")
    recent_legislative_record: list[str] | None = Field(default=None, description="Key legislative measures they recently supported or opposed. Each item is one measure. Embed inline citation markers like [1], [2] referencing the recent_legislative_record_citations list. Max 3-5 items.")
    recent_legislative_record_citations: list[Citation] = Field(default_factory=list, description="Ordered list of sources for recent_legislative_record section.")
    accomplishments: list[str] | None = Field(default=None, description="Notable achievements, successful initiatives, awards. Each item is one accomplishment. Embed inline citation markers like [1], [2] referencing the accomplishments_citations list. Max 3-5 items.")
    accomplishments_citations: list[Citation] = Field(default_factory=list, description="Ordered list of sources for accomplishments section.")
    controversies: list[str] | None = Field(default=None, description="Scandals, ethics complaints, controversial actions or statements. Each item is one controversy. Embed inline citation markers like [1], [2] referencing the controversies_citations list. Max 3-5 items.")
    controversies_citations: list[Citation] = Field(default_factory=list, description="Ordered list of sources for controversies section.")
    recent_press: list[str] | None = Field(default=None, description="Recent press coverage, public statements, local news. Each item is one story or event. Embed inline citation markers like [1], [2] referencing the recent_press_citations list. Max 3-5 items.")
    recent_press_citations: list[Citation] = Field(default_factory=list, description="Ordered list of sources for recent_press section.")
    top_donors: list[str] | None = Field(default=None, description="Largest political donors, five max. Each item is one donor. Embed inline citation markers like [1], [2] referencing the top_donors_citations list. Max 3-5 items.")
    top_donors_citations: list[Citation] = Field(default_factory=list, description="Ordered list of sources for top_donors section.")

    _NOT_FOUND = "Information not found."

    SECTION_NAMES: list[str] = Field(default=[
        "background", "policy_positions", "recent_legislative_record",
        "accomplishments", "controversies", "recent_press", "top_donors",
    ], exclude=True)

    @model_validator(mode="after")
    def fill_missing_fields(self) -> "ResearchSummary":
        """Fill empty-but-present fields with fallback text. None means still loading."""
        fallback = self._NOT_FOUND
        for field_name in self.SECTION_NAMES:
            value = getattr(self, field_name)
            if value is None:
                continue  # Still loading — leave as None
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


class RepresentativesResponse(BaseModel):
    representatives: list[Representative]


class PollingLocation(BaseModel):
    name: str
    address: str
    hours: str | None = None


class Candidate(BaseModel):
    name: str
    office: str
    level: str  # "federal" | "state" | "municipal"
    party: str | None = None
    photo_url: str | None = None
    contest_name: str = ""
    incumbent: bool = False

    def to_representative(self) -> "Representative":
        """Convert to Representative shape for the research endpoint."""
        return Representative(
            name=self.name,
            office=self.office,
            level=self.level,
            party=self.party,
            photo_url=self.photo_url,
        )


class Contest(BaseModel):
    office: str
    level: str  # "federal" | "state" | "municipal"
    district_name: str | None = None
    candidates: list[Candidate] = []


class VoterInfo(BaseModel):
    """Parsed from Google Civic API state[].electionAdministrationBody. No research needed."""
    registration_url: str | None = None
    absentee_url: str | None = None
    ballot_info_url: str | None = None
    polling_location_url: str | None = None
    early_vote_sites: list[PollingLocation] = []
    drop_off_locations: list[PollingLocation] = []
    mail_only: bool = False
    admin_body_name: str | None = None
    admin_body_url: str | None = None


class Election(BaseModel):
    name: str
    date: str  # ISO format
    election_type: str  # "primary" | "general" | "runoff"
    polling_location: PollingLocation | None = None
    voter_info: VoterInfo | None = None
    contests: list[Contest] = []


class ElectionsResponse(BaseModel):
    elections: list[Election]
    research_ids: dict[str, str] = Field(default_factory=dict)  # key: "election_name|date" → research_id


class ElectionResearchSummary(BaseModel):
    """Two sections: election_context (sync LLM, no search) + key_issues_and_significance (async, web search)."""
    election_context: str | None = None
    key_issues_and_significance: str | None = None
    citations: list[Citation] = Field(default_factory=list)

    SECTION_NAMES: list[str] = Field(default=[
        "election_context", "key_issues_and_significance",
    ], exclude=True)


class ElectionResearchRequest(BaseModel):
    election_name: str
    election_date: str
    election_type: str
    state: str
    address: str


class ElectionResearchResponse(BaseModel):
    research_id: str
    status: Literal["pending", "in_progress", "complete", "failed"]
    summary: ElectionResearchSummary | None = None


class ResearchRequest(BaseModel):
    representative: Representative


class ResearchResponse(BaseModel):
    research_id: str
    status: Literal["pending", "in_progress", "complete", "failed"]
    summary: ResearchSummary | None = None


class TransactionCreate(BaseModel):
    type: Literal["inflow", "outflow"]
    source: str
    billing_model: Literal["per_request", "bulk", "subscription"]
    amount_usd: float
    description: str | None = None
    research_task_id: str | None = None


class TransactionOut(BaseModel):
    id: int
    type: str
    source: str
    billing_model: str
    amount_usd: Decimal
    description: str | None
    research_task_id: str | None
    created_at: datetime
    balance_after: Decimal | None
