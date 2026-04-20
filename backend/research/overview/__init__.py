"""Dispatch to the active rep overview pipeline version.

Selected at import time via the ``OVERVIEW_PIPELINE_VERSION`` env var.
Supported values: ``v1`` (default), ``v1_1``, ``v2``.

Each version's package must export ``ResearchSummary``,
``research_representative``, and ``TOTAL_SECTIONS``.
"""

import os

ACTIVE_VERSION = os.getenv("OVERVIEW_PIPELINE_VERSION", "v1")

if ACTIVE_VERSION == "v1":
    from .v1 import ResearchSummary, TOTAL_SECTIONS, research_representative
elif ACTIVE_VERSION == "v1_1":
    from .v1_1 import ResearchSummary, TOTAL_SECTIONS, research_representative
elif ACTIVE_VERSION == "v2":
    from .v2 import ResearchSummary, TOTAL_SECTIONS, research_representative
else:
    raise ValueError(
        f"Unknown OVERVIEW_PIPELINE_VERSION: {ACTIVE_VERSION!r}. "
        "Expected one of: v1, v1_1, v2."
    )

__all__ = [
    "ACTIVE_VERSION",
    "ResearchSummary",
    "TOTAL_SECTIONS",
    "research_representative",
]
