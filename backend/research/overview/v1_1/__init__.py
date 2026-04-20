from .models import ResearchSummary

TOTAL_SECTIONS = 1

# research_representative is imported from .pipeline in Task 9.
# For now, __all__ does not include it to avoid import error before Task 9.
__all__ = ["ResearchSummary", "TOTAL_SECTIONS"]
