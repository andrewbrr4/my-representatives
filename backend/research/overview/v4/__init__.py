"""v4 overview pipeline — LangGraph-native breadth-first + adaptive-depth.

Exports the v3-compatible contract: ``ResearchSummary``,
``research_representative``, and ``TOTAL_SECTIONS``. ``TOTAL_SECTIONS=1``
because the entire pipeline writes once to the InMemoryResearchStore at
the end (no per-section streaming).
"""

from research.overview.v4.models import ResearchSummary
from research.overview.v4.pipeline import research_representative

TOTAL_SECTIONS = 1

__all__ = ["ResearchSummary", "TOTAL_SECTIONS", "research_representative"]
