"""v3 overview pipeline — breadth-first retrieval + single-shot distillation.

Flow:
1. Query generation (1 LLM call, no tools) → list of diverse search queries.
2. Parallel Tavily fan-out (no LLM in the loop).
3. Pre-filter (dedupe by URL, truncate snippets, cap total count).
4. Distillation (1 LLM call, no tools) → BulletsResearchSummary.
"""

import asyncio
import logging
import os
from datetime import date
from pathlib import Path
from string import Template

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langfuse import observe
from langfuse.langchain import CallbackHandler
from pydantic import BaseModel, Field

from models import Representative
from research.overview.v3.models import ResearchSummary
from research.overview.v3.prefilter import prefilter_results
from research.search import tavily_search_raw
from research.usage import UsageStats, UsageTracker
from store.research_store import InMemoryResearchStore

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

_NUM_QUERIES = int(os.getenv("OVERVIEW_V3_NUM_QUERIES", "15"))
_RESULTS_PER_QUERY = int(os.getenv("OVERVIEW_V3_RESULTS_PER_QUERY", "5"))
_SEARCH_CONCURRENCY = int(os.getenv("OVERVIEW_V3_SEARCH_CONCURRENCY", "5"))
_RESULTS_CEILING = int(os.getenv("OVERVIEW_V3_RESULTS_CEILING", "60"))
_SNIPPET_CHAR_CAP = int(os.getenv("OVERVIEW_V3_SNIPPET_CHAR_CAP", "800"))


class _QueryList(BaseModel):
    queries: list[str] = Field(description="Diverse search queries, one per item.")


@observe(name="v3-query-gen")
async def generate_queries(rep: Representative) -> tuple[list[str], UsageStats]:
    langfuse_handler = CallbackHandler()
    usage_tracker = UsageTracker()

    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    )
    structured = model.with_structured_output(_QueryList)

    system_template = Template((_PROMPTS_DIR / "query_gen_system.txt").read_text())
    user_template = Template((_PROMPTS_DIR / "query_gen_user.txt").read_text())

    system_prompt = system_template.substitute(
        current_date=date.today().isoformat(), num_queries=str(_NUM_QUERIES)
    )
    user_prompt = user_template.substitute(
        name=rep.name, office=rep.office, num_queries=str(_NUM_QUERIES)
    )

    result = await structured.ainvoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
        config={
            "callbacks": [langfuse_handler, usage_tracker],
            "run_name": f"v3:query-gen:{rep.name}",
        },
    )
    queries = [q.strip() for q in result.queries if q and q.strip()]
    logger.info(f"[v3] Generated {len(queries)} queries for {rep.name}")
    return queries, usage_tracker.stats


async def run_searches(queries: list[str]) -> tuple[list[dict[str, str]], int]:
    """Run all queries in parallel with a concurrency bound.

    Returns ``(concatenated_results, num_successful_queries)``.
    A query is "successful" if it returned at least one result.
    """
    sem = asyncio.Semaphore(_SEARCH_CONCURRENCY)

    async def _run_one(q: str) -> list[dict[str, str]]:
        async with sem:
            return await tavily_search_raw(q, max_results=_RESULTS_PER_QUERY)

    per_query = await asyncio.gather(*(_run_one(q) for q in queries))
    concatenated: list[dict[str, str]] = []
    successful = 0
    for results in per_query:
        if results:
            successful += 1
            concatenated.extend(results)
    logger.info(
        f"[v3] Search phase: {successful}/{len(queries)} queries returned results; "
        f"{len(concatenated)} total raw results"
    )
    return concatenated, successful


def _format_results_block(results: list[dict[str, str]]) -> str:
    if not results:
        return "(no results)"
    lines: list[str] = []
    for i, r in enumerate(results, start=1):
        lines.append(f"[{i}] {r['title']}\n    URL: {r['url']}\n    {r['snippet']}")
    return "\n\n".join(lines)


@observe(name="v3-distill")
async def distill(
    rep: Representative, results: list[dict[str, str]]
) -> tuple[ResearchSummary, UsageStats]:
    langfuse_handler = CallbackHandler()
    usage_tracker = UsageTracker()

    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    )
    structured = model.with_structured_output(ResearchSummary)

    system_template = Template((_PROMPTS_DIR / "distill_system.txt").read_text())
    user_template = Template((_PROMPTS_DIR / "distill_user.txt").read_text())

    system_prompt = system_template.substitute(current_date=date.today().isoformat())
    user_prompt = user_template.substitute(
        name=rep.name, office=rep.office, results_block=_format_results_block(results)
    )

    summary = await structured.ainvoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
        config={
            "callbacks": [langfuse_handler, usage_tracker],
            "run_name": f"v3:distill:{rep.name}",
        },
    )
    logger.info(
        f"[v3] Distill complete for {rep.name}: "
        f"{len(summary.bullets or [])} bullets / {len(summary.citations)} citations"
    )
    return summary, usage_tracker.stats


@observe(name="v3-research-pipeline")
async def research_representative(
    rep: Representative,
    store: InMemoryResearchStore | None = None,
    research_id: str | None = None,
) -> tuple[ResearchSummary | None, UsageStats]:
    total_usage = UsageStats()
    logger.info(f"[v3] Starting research for {rep.name}")

    try:
        queries, usage = await generate_queries(rep)
    except Exception as e:
        logger.error(f"[v3] Query generation failed for {rep.name}: {e}", exc_info=True)
        return None, total_usage
    total_usage += usage
    if not queries:
        logger.error(f"[v3] Query generation returned no queries for {rep.name}")
        return None, total_usage

    raw_results, successful_queries = await run_searches(queries)
    total_usage.tool_calls += successful_queries
    if not raw_results:
        logger.error(f"[v3] All searches returned no results for {rep.name}")
        return None, total_usage

    filtered = prefilter_results(
        raw_results, snippet_char_cap=_SNIPPET_CHAR_CAP, ceiling=_RESULTS_CEILING
    )
    logger.info(f"[v3] Pre-filter: {len(raw_results)} → {len(filtered)} results")

    try:
        summary, usage = await distill(rep, filtered)
    except Exception as e:
        logger.error(f"[v3] Distillation failed for {rep.name}: {e}", exc_info=True)
        return None, total_usage
    total_usage += usage

    if store and research_id:
        # section_name must match a field on BulletsResearchSummary — use "bullets"
        # so InMemoryResearchStore.complete_section writes to summary.bullets.
        await store.complete_section(
            research_id, "bullets", summary.bullets or [], summary.citations
        )

    logger.info(
        f"[v3] Research for {rep.name}: "
        f"{total_usage.input_tokens} in / {total_usage.output_tokens} out / "
        f"{total_usage.tool_calls} tool calls"
    )
    return summary, total_usage
