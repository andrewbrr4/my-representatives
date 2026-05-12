"""v4 overview output schema and internal types.

``ResearchSummary`` matches the frontend ``BulletsResearchSummary`` contract
(same shape as v2/v3): ``bullets: list[str]`` (required, non-nullable —
empty list = loading state) plus ``citations: list[Citation]``.

``SearchResult`` is internal to v4 and shuttles data between nodes,
intentionally lightweight to keep token footprint predictable. Both
breadth (Tavily fan-out) and depth (per-topic subagent) emit the same
``SearchResult`` shape; the optional ``topic`` field is set on
depth-derived results so the formatter can label them.
"""

from pydantic import BaseModel, Field

from models import Citation, SourceLink
from research.overview._bullet_coercion import BulletList


class SearchResult(BaseModel):
    """Single Tavily search result. Mirrors the dict shape returned by
    ``research.search.tavily_search_raw`` but typed for clarity inside v4.

    ``topic`` is empty for breadth results; depth results are tagged with
    the subtopic the depth subagent was asked to investigate.
    """

    url: str
    title: str
    snippet: str
    published_date: str = ""
    topic: str = ""


class ResearchSummary(BaseModel):
    """v4's user-facing output. Same shape as v2/v3, plus an optional
    ``sources`` list (deduped breadth+depth pool) when the show-sources
    flag is enabled."""

    bullets: BulletList = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    sources: list[SourceLink] = Field(default_factory=list)


__all__ = ["Citation", "ResearchSummary", "SearchResult", "SourceLink"]
