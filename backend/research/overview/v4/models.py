"""v4 overview output schema and internal types.

``ResearchSummary`` matches the frontend ``BulletsResearchSummary`` contract
(same shape as v2/v3): ``bullets: list[str]`` (required, non-nullable —
empty list = loading state) plus ``citations: list[Citation]``.

``Finding`` and ``SearchResult`` are internal to v4 and shuttle data
between nodes. Both intentionally lightweight to keep token footprint
predictable across the pipeline.
"""

from pydantic import BaseModel, Field

from models import Citation
from research.overview._bullet_coercion import BulletList


class SearchResult(BaseModel):
    """Single Tavily search result. Mirrors the dict shape returned by
    ``research.search.tavily_search_raw`` but typed for clarity inside v4."""

    url: str
    title: str
    snippet: str
    published_date: str = ""


class Finding(BaseModel):
    """One factual claim about the rep, with the source URLs that support it.

    Produced by the research_agent (from filtered breadth results) and
    by depth subagents (from focused per-topic searches). Consumed by
    the formatter, which renders bullets and assembles the unified
    citation list from ``source_urls``.
    """

    claim: str = Field(description="One-sentence factual statement.")
    source_urls: list[str] = Field(
        default_factory=list,
        description="URLs from the search pool that support this claim.",
    )
    topic: str = Field(
        default="",
        description="Rough category, e.g. 'policy', 'record', 'controversy'.",
    )


class ResearchSummary(BaseModel):
    """v4's user-facing output. Same shape as v2/v3."""

    bullets: BulletList = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


__all__ = ["Citation", "Finding", "ResearchSummary", "SearchResult"]
