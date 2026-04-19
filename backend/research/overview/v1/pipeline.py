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

from models import (
    Citation,
    ListSectionResult,
    Representative,
)
from research.overview.v1.models import ResearchSummary
from research.search import web_search
from research.usage import UsageStats, UsageTracker
from store.research_store import InMemoryResearchStore

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# Limit concurrent research calls to avoid rate limits
_semaphore = asyncio.Semaphore(2)


@dataclass
class SectionConfig:
    name: str
    output_model: type[BaseModel]
    system_prompt_file: str
    user_prompt_file: str
    content_field: str  # "content" for SectionResult, "items" for ListSectionResult


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


@observe(name="section-agent")
async def run_section_agent(
    rep: Representative, section: SectionConfig
) -> tuple[str | list[str], list[Citation], UsageStats]:
    """Run a focused agent for one section of the research summary."""
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

    system_template = Template(
        (_PROMPTS_DIR / section.system_prompt_file).read_text()
    )
    user_template = Template(
        (_PROMPTS_DIR / section.user_prompt_file).read_text()
    )

    system_prompt = system_template.substitute(
        current_date=date.today().isoformat()
    )
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
            "run_name": f"{section.name}:{rep.name}",
        },
    )

    structured = result["structured_response"]
    content = getattr(structured, section.content_field)
    citations = structured.citations
    logger.info(
        f"Section '{section.name}' complete for {rep.name}: "
        f"{len(citations)} citations"
    )
    return content, citations, usage_tracker.stats


@observe(name="research-pipeline")
async def research_representative(
    rep: Representative,
    store: InMemoryResearchStore | None = None,
    research_id: str | None = None,
) -> tuple[ResearchSummary | None, UsageStats]:
    """Run 5 focused section agents concurrently, writing each section to store as it completes."""
    total_usage = UsageStats()
    usage_lock = asyncio.Lock()
    logger.info(f"Queued research for {rep.name}")

    async def _run_and_store(section: SectionConfig) -> None:
        """Run one section agent and write result to store immediately."""
        try:
            content, citations, usage = await run_section_agent(rep, section)
        except Exception as e:
            logger.error(
                f"Section '{section.name}' failed for {rep.name}: {e}",
                exc_info=e,
            )
            content = "" if section.content_field == "content" else []
            citations = []
            usage = UsageStats()

        async with usage_lock:
            nonlocal total_usage
            total_usage += usage

        if store and research_id:
            await store.complete_section(research_id, section.name, content, citations)

    async with _semaphore:
        logger.info(f"Starting research for {rep.name}")
        try:
            await asyncio.gather(*(_run_and_store(section) for section in SECTIONS))

            logger.info(
                f"Research for {rep.name}: "
                f"{total_usage.input_tokens} in / {total_usage.output_tokens} out / "
                f"{total_usage.tool_calls} tool calls"
            )

            # Read the assembled summary from the store
            if store and research_id:
                task = await store.get(research_id)
                return task.summary if task else None, total_usage

            return None, total_usage
        except Exception as e:
            logger.error(f"Research failed for {rep.name}: {e}", exc_info=True)
            return None, total_usage
