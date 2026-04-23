"""v2 overview pipeline.

Flow:
1. Run 5 per-section research agents concurrently (own copy of v1's structure).
2. Assemble a dossier + unified citation pool.
3. One non-tool LLM call synthesizes 5–8 blended bullets with inline [N] markers.

Nothing is imported from ``research.overview.v1``. This version owns its
section agents and prompts end-to-end.
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from string import Template

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langfuse import observe
from langfuse.langchain import CallbackHandler
from langchain.agents import create_agent
from pydantic import BaseModel

from models import Citation, ListSectionResult, Representative
from research.overview._bullet_coercion import BulletList
from research.overview.v2.models import ResearchSummary
from research.overview.v2.synthesis_input import DossierResult, build_dossier
from research.search import web_search
from research.usage import UsageStats, UsageTracker
from store.research_store import InMemoryResearchStore


class _SynthesisBullets(BaseModel):
    # Synthesis only needs bullets from the LLM — citations are assembled in
    # Python from the already-built unified pool. Keeping this schema to a
    # single required ``list[str]`` avoids the ``anyOf`` shape that trips
    # Anthropic's tool-use encoder.
    bullets: BulletList

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# v2 owns its own semaphore — isolated from v1's.
_semaphore = asyncio.Semaphore(2)


@dataclass
class SectionConfig:
    name: str
    output_model: type[BaseModel]
    system_prompt_file: str
    user_prompt_file: str
    content_field: str  # "items" for ListSectionResult


SECTIONS: list[SectionConfig] = [
    SectionConfig(
        name="policy_positions",
        output_model=ListSectionResult,
        system_prompt_file="policy_positions_system.txt",
        user_prompt_file="policy_positions_user.txt",
        content_field="items",
    ),
    SectionConfig(
        name="recent_legislative_record",
        output_model=ListSectionResult,
        system_prompt_file="recent_legislative_record_system.txt",
        user_prompt_file="recent_legislative_record_user.txt",
        content_field="items",
    ),
    SectionConfig(
        name="accomplishments",
        output_model=ListSectionResult,
        system_prompt_file="accomplishments_system.txt",
        user_prompt_file="accomplishments_user.txt",
        content_field="items",
    ),
    SectionConfig(
        name="controversies",
        output_model=ListSectionResult,
        system_prompt_file="controversies_system.txt",
        user_prompt_file="controversies_user.txt",
        content_field="items",
    ),
    SectionConfig(
        name="top_donors",
        output_model=ListSectionResult,
        system_prompt_file="top_donors_system.txt",
        user_prompt_file="top_donors_user.txt",
        content_field="items",
    ),
]


@observe(name="v2-section-agent")
async def run_section_agent(
    rep: Representative, section: SectionConfig
) -> tuple[list[str], list[Citation], UsageStats]:
    """Run a focused agent for one section. Returns (items, citations, usage)."""
    langfuse_handler = CallbackHandler()
    usage_tracker = UsageTracker()
    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    )
    agent = create_agent(
        model,
        tools=[web_search],
        response_format=section.output_model,
    )

    system_template = Template((_PROMPTS_DIR / section.system_prompt_file).read_text())
    user_template = Template((_PROMPTS_DIR / section.user_prompt_file).read_text())

    system_prompt = system_template.substitute(current_date=date.today().isoformat())
    user_prompt = user_template.substitute(name=rep.name, office=rep.office)

    result = await agent.ainvoke(
        {
            "messages": [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        },
        config={
            "callbacks": [langfuse_handler, usage_tracker],
            "recursion_limit": 15,
            "run_name": f"v2:{section.name}:{rep.name}",
        },
    )

    structured = result["structured_response"]
    items: list[str] = getattr(structured, section.content_field)
    citations: list[Citation] = structured.citations
    logger.info(
        f"[v2] Section '{section.name}' complete for {rep.name}: "
        f"{len(citations)} citations"
    )
    return items, citations, usage_tracker.stats


def _format_citations_block(citations: list[Citation]) -> str:
    if not citations:
        return "(none)"
    lines = []
    for i, c in enumerate(citations):
        suffix = f" (Published: {c.published_date})" if c.published_date else ""
        lines.append(f"[{i + 1}] {c.title} — {c.url}{suffix}")
    return "\n".join(lines)


@observe(name="v2-synthesis")
async def run_synthesis(
    rep: Representative, dossier_result: DossierResult
) -> tuple[ResearchSummary, UsageStats]:
    """Non-tool LLM call that collapses the dossier into 5–8 bullets."""
    langfuse_handler = CallbackHandler()
    usage_tracker = UsageTracker()

    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    )
    structured_model = model.with_structured_output(_SynthesisBullets)

    system_template = Template((_PROMPTS_DIR / "synthesis_system.txt").read_text())
    user_template = Template((_PROMPTS_DIR / "synthesis_user.txt").read_text())

    system_prompt = system_template.substitute(current_date=date.today().isoformat())
    user_prompt = user_template.substitute(
        name=rep.name,
        office=rep.office,
        dossier=dossier_result.dossier or "(no section content returned)",
        citations_block=_format_citations_block(dossier_result.unified_citations),
    )

    result = await structured_model.ainvoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
        config={
            "callbacks": [langfuse_handler, usage_tracker],
            "run_name": f"v2:synthesis:{rep.name}",
        },
    )

    summary = ResearchSummary(
        bullets=result.bullets,
        citations=dossier_result.unified_citations,
    )
    logger.info(
        f"[v2] Synthesis complete for {rep.name}: "
        f"{len(summary.bullets)} bullets / {len(summary.citations)} citations"
    )
    return summary, usage_tracker.stats


@observe(name="v2-research-pipeline")
async def research_representative(
    rep: Representative,
    store: InMemoryResearchStore | None = None,
    research_id: str | None = None,
) -> tuple[ResearchSummary | None, UsageStats]:
    """Run 5 section agents concurrently, then synthesize into blended bullets."""
    total_usage = UsageStats()
    usage_lock = asyncio.Lock()
    logger.info(f"[v2] Queued research for {rep.name}")

    section_results: dict[str, tuple[list[str], list[Citation]]] = {}
    section_lock = asyncio.Lock()

    async def _run_section(section: SectionConfig) -> None:
        try:
            items, citations, usage = await run_section_agent(rep, section)
        except Exception as e:
            logger.error(
                f"[v2] Section '{section.name}' failed for {rep.name}: {e}",
                exc_info=e,
            )
            items = []
            citations = []
            usage = UsageStats()

        async with usage_lock:
            nonlocal total_usage
            total_usage += usage
        async with section_lock:
            section_results[section.name] = (items, citations)

    async with _semaphore:
        logger.info(f"[v2] Starting research for {rep.name}")
        try:
            await asyncio.gather(*(_run_section(section) for section in SECTIONS))
        except Exception as e:
            logger.error(
                f"[v2] Unexpected error in section orchestration for {rep.name}: {e}",
                exc_info=True,
            )
            return None, total_usage

        # Preserve section ordering from SECTIONS (deterministic dossier).
        ordered = [
            (s.name, *section_results.get(s.name, ([], []))) for s in SECTIONS
        ]
        dossier_result = build_dossier(ordered)

        try:
            summary, synth_usage = await run_synthesis(rep, dossier_result)
        except Exception as e:
            logger.error(f"[v2] Synthesis failed for {rep.name}: {e}", exc_info=True)
            return None, total_usage

        async with usage_lock:
            total_usage += synth_usage

        if store and research_id:
            # total_sections=1 → a single complete_section call moves the task to "complete".
            await store.complete_section(
                research_id,
                "bullets",
                summary.bullets,
                summary.citations,
            )

        logger.info(
            f"[v2] Research for {rep.name}: "
            f"{total_usage.input_tokens} in / {total_usage.output_tokens} out / "
            f"{total_usage.tool_calls} tool calls"
        )
        return summary, total_usage
