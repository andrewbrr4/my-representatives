from .models import ResearchSummary

TOTAL_SECTIONS = 1

# `research_representative` is defined in .pipeline starting in Task 9.
# Until then, re-exporting it here would create a circular import:
# pipeline.py imports ResearchSummary from .models, which would require
# this __init__.py to finish loading first.
__all__ = ["ResearchSummary", "TOTAL_SECTIONS"]
