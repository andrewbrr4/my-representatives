from datetime import datetime
from decimal import Decimal
from typing import ClassVar, Literal

from pydantic import BaseModel, Field


# =============================================================================
# Non-research models
# =============================================================================


class AddressRequest(BaseModel):
    address: str


class Contact(BaseModel):
    website: str | None = None
    phone: str | None = None
    email: str | None = None


class Citation(BaseModel):
    title: str
    url: str
    published_date: str | None = None


class SourceLink(BaseModel):
    """User-facing 'further reading' entry — the deduped Tavily pool that
    informed a research summary. Distinct from ``Citation``: citations
    enforce trust on specific bullets via inline ``[N]`` markers, while
    SourceLinks are the broader exploration pool for the user."""
    title: str
    url: str


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


class BallotMeasure(BaseModel):
    title: str
    description: str
    responses: list[str] = []  # e.g. ["Yes", "No"]
    district_name: str | None = None
    district_scope: str | None = None  # "statewide", "municipal", etc.


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
    ballot_measures: list[BallotMeasure] = []


class ElectionsResponse(BaseModel):
    elections: list[Election]
    research_ids: dict[str, str] = Field(default_factory=dict)  # key: "election_name|date" → research_id


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


# =============================================================================
# Research models
# =============================================================================

# --- Shared research primitives ---


class SectionResult(BaseModel):
    content: str
    citations: list[Citation]


class ListSectionResult(BaseModel):
    items: list[str]
    citations: list[Citation]


# --- Rep overview research ---
# ResearchSummary, ResearchRequest, ResearchResponse are version-specific.
# Import from research.overview to get the active version's model.
# Request/Response models live in routers/overview.py.


# --- Issue overview research ---


class IssueStanceSummary(BaseModel):
    """Single-section summary: where a rep stands on a specific issue."""
    stance_summary: list[str] | None = None
    citations: list[Citation] = Field(default_factory=list)
    further_reading: list[SourceLink] = Field(default_factory=list)


class IssueInfo(BaseModel):
    id: str
    label: str


class IssueResearchRequest(BaseModel):
    representative: Representative
    query: str


class IssueResearchResponse(BaseModel):
    research_id: str | None = None
    status: Literal["pending", "in_progress", "complete", "failed", "no_match"]
    issue: IssueInfo | None = None
    summary: IssueStanceSummary | None = None
    message: str | None = None


# --- Elections research ---


class ElectionResearchSummary(BaseModel):
    """Single-section ballot overview: conversational paragraph explaining what's on the ballot."""
    ballot_overview: str | None = None

    SECTION_NAMES: ClassVar[list[str]] = [
        "ballot_overview",
    ]


class ElectionResearchRequest(BaseModel):
    election_name: str
    election_date: str
    election_type: str
    state: str
    address: str
    contests: list[Contest] = []
    ballot_measures: list[BallotMeasure] = []


class ElectionResearchResponse(BaseModel):
    research_id: str
    status: Literal["pending", "in_progress", "complete", "failed"]
    summary: ElectionResearchSummary | None = None
