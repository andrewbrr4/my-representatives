"""LangChain ``@tool`` for the depth subagent's web search.

Re-exports ``research.search.web_search`` unchanged. v4 keeps the import
local so the depth subgraph reads as self-contained and so we can swap in
a v4-specific variant later without touching shared code.
"""

from research.search import web_search

depth_web_search = web_search

__all__ = ["depth_web_search"]
