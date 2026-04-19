"""V1 rep overview models — 5 independent per-section agents, each with own citations."""

from typing import ClassVar

from pydantic import BaseModel, Field, model_validator

from models import Citation


class ResearchSummary(BaseModel):
    policy_positions: list[str] | None = Field(default=None, description="Where they stand on key issues based on voting record and public statements, not campaign messaging. Each item is one policy area. Embed inline citation markers like [1], [2] referencing the policy_positions_citations list. Max 3-5 items.")
    policy_positions_citations: list[Citation] = Field(default_factory=list, description="Ordered list of sources for policy_positions section.")
    recent_legislative_record: list[str] | None = Field(default=None, description="Key legislative measures they recently supported or opposed. Each item is one measure. Embed inline citation markers like [1], [2] referencing the recent_legislative_record_citations list. Max 3-5 items.")
    recent_legislative_record_citations: list[Citation] = Field(default_factory=list, description="Ordered list of sources for recent_legislative_record section.")
    accomplishments: list[str] | None = Field(default=None, description="Notable achievements, successful initiatives, awards. Each item is one accomplishment. Embed inline citation markers like [1], [2] referencing the accomplishments_citations list. Max 3-5 items.")
    accomplishments_citations: list[Citation] = Field(default_factory=list, description="Ordered list of sources for accomplishments section.")
    controversies: list[str] | None = Field(default=None, description="Scandals, ethics complaints, controversial actions or statements. Each item is one controversy. Embed inline citation markers like [1], [2] referencing the controversies_citations list. Max 3-5 items.")
    controversies_citations: list[Citation] = Field(default_factory=list, description="Ordered list of sources for controversies section.")
    top_donors: list[str] | None = Field(default=None, description="Largest political donors, five max. Each item is one donor. Embed inline citation markers like [1], [2] referencing the top_donors_citations list. Max 3-5 items.")
    top_donors_citations: list[Citation] = Field(default_factory=list, description="Ordered list of sources for top_donors section.")

    _NOT_FOUND = "Information not found."

    SECTION_NAMES: ClassVar[list[str]] = [
        "policy_positions", "recent_legislative_record",
        "accomplishments", "controversies", "top_donors",
    ]

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
