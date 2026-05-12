"""v4 overview pipeline — top-level StateGraph wiring + entrypoint.

Flow:
  query_generator → breadth_search → filter → research_agent → formatter

The research_agent node performs structured-output triage and fans out
selected depth subagents in parallel via ``asyncio.gather`` (see
``nodes/research_agent.py`` and ``nodes/depth_subgraph.py``).
"""

import logging
import os

from langfuse import observe
from langgraph.graph import END, START, StateGraph

from models import Representative
from research.overview.models import ResearchSummary
from research.overview.nodes.breadth_search import breadth_search
from research.overview.nodes.filter_node import filter_node
from research.overview.nodes.formatter import formatter
from research.overview.nodes.query_generator import query_generator
from research.overview.nodes.research_agent import research_agent_node
from research.overview.state import V4State
from research.usage import UsageStats
from store.research_store import InMemoryResearchStore

logger = logging.getLogger(__name__)


def build_pipeline_graph():
    g = StateGraph(V4State)
    g.add_node("query_generator", query_generator)
    g.add_node("breadth_search", breadth_search)
    g.add_node("filter", filter_node)
    g.add_node("research_agent", research_agent_node)
    g.add_node("formatter", formatter)
    g.add_edge(START, "query_generator")
    g.add_edge("query_generator", "breadth_search")
    g.add_edge("breadth_search", "filter")
    g.add_edge("filter", "research_agent")
    g.add_edge("research_agent", "formatter")
    g.add_edge("formatter", END)
    return g.compile()


# Module-level compiled graph; LangGraph compiled graphs are stateless
# and reusable across runs.
pipeline_graph = build_pipeline_graph()


@observe(name="v4-research-pipeline")
async def research_representative(
    rep: Representative,
    store: InMemoryResearchStore | None = None,
    research_id: str | None = None,
) -> tuple[ResearchSummary | None, UsageStats]:
    """Public entrypoint matching the v1/v2/v3 contract."""
    total = UsageStats()
    logger.info(f"[v4] Starting research for {rep.name}")

    initial: V4State = {"rep": rep, "usage_log": []}
    try:
        result = await pipeline_graph.ainvoke(
            initial,
            config={"run_name": f"v4:pipeline:{rep.name}"},
        )
    except Exception as e:
        logger.error(f"[v4] Pipeline failed for {rep.name}: {e}", exc_info=True)
        return None, total

    for stats in result.get("usage_log") or []:
        total += stats

    summary = result.get("summary")
    if summary is None:
        logger.error(f"[v4] Pipeline returned no summary for {rep.name}")
        return None, total

    if store and research_id:
        # When show-sources is on, ``summary.sources`` needs to reach the
        # task store too. ``complete_section`` only writes bullets+citations,
        # so we use ``complete()`` (full-summary atomic write) for that
        # path. With TOTAL_SECTIONS=1 the two paths are functionally
        # equivalent for v4 — ``complete_section`` is kept on the default
        # path purely to minimize blast radius behind the flag.
        show_sources = os.getenv("OVERVIEW_V4_SHOW_SOURCES", "").strip().lower() in (
            "1", "true", "yes", "on"
        )
        if show_sources:
            await store.complete(research_id, summary)
        else:
            await store.complete_section(
                research_id, "bullets", summary.bullets, summary.citations
            )

    logger.info(
        f"[v4] Research for {rep.name}: "
        f"{total.input_tokens} in / {total.output_tokens} out / "
        f"{total.tool_calls} tool calls; "
        f"{len(summary.bullets)} bullets / {len(summary.citations)} citations"
    )
    return summary, total
