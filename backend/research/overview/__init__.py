"""Dispatch to the active rep overview pipeline version.

Default is ``v4`` (the flat top-level pipeline). The ``OVERVIEW_PIPELINE_VERSION``
env var (read at import time) can select a legacy variant for trace/cost
comparison: ``v1``, ``v2``, ``v3`` — all loaded from ``research.overview.legacy.*``.

Each selected version exports ``ResearchSummary``, ``research_representative``,
and ``TOTAL_SECTIONS`` from this module.
"""

import os

ACTIVE_VERSION = os.getenv("OVERVIEW_PIPELINE_VERSION", "v4")

if ACTIVE_VERSION == "v4":
    from .v4 import ResearchSummary, TOTAL_SECTIONS, research_representative
elif ACTIVE_VERSION == "v1":
    from .legacy.v1 import ResearchSummary, TOTAL_SECTIONS, research_representative
elif ACTIVE_VERSION == "v2":
    from .legacy.v2 import ResearchSummary, TOTAL_SECTIONS, research_representative
elif ACTIVE_VERSION == "v3":
    from .legacy.v3 import ResearchSummary, TOTAL_SECTIONS, research_representative
else:
    raise ValueError(
        f"Unknown OVERVIEW_PIPELINE_VERSION: {ACTIVE_VERSION!r}. "
        "Expected one of: v1, v2, v3, v4."
    )

__all__ = [
    "ACTIVE_VERSION",
    "ResearchSummary",
    "TOTAL_SECTIONS",
    "research_representative",
]
