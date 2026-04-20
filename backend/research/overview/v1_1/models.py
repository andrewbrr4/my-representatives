"""v1.1 re-exports the shared BulletsResearchSummary as ResearchSummary.

The schema is shared because the design treats it as a cross-version contract,
not version-specific logic. All section-agent code and prompts are owned
by v1.1 directly and do not import from v1.
"""

from research.overview.shared.models import BulletsResearchSummary as ResearchSummary

__all__ = ["ResearchSummary"]
