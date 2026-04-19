"""Shared output schema for rep overview versions v1.1+ that emit a single
blended bullet list (no per-section breakdown).

Version-specific pipelines (v1_1, v2) re-export this as ``ResearchSummary``
from their own ``__init__.py`` so ``research.overview.__init__.py`` dispatch
works transparently.
"""

from pydantic import BaseModel, Field

from models import Citation


class BulletsResearchSummary(BaseModel):
    """5–8 one-liner bullets blended across all topics, with a unified citation list.

    Each bullet may contain inline markers like ``[1]`` / ``[2]`` referencing
    1-indexed positions in ``citations``.
    """

    bullets: list[str] | None = Field(
        default=None,
        description="5–8 one-liner bullets. None means still loading.",
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Unified, renumbered citation list. 1-indexed by inline [N] markers in bullets.",
    )
