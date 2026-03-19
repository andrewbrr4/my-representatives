import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from string import Template

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langfuse import observe
from langfuse.langchain import CallbackHandler
from langchain.agents import create_agent
from pydantic import BaseModel

from models import (
    Citation,
    ListSectionResult,
    Representative,
    ResearchSummary,
    SectionResult,
)
from research.search import web_search_impl
from research.usage import UsageStats, UsageTracker

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# Limit concurrent research calls to avoid rate limits
_semaphore = asyncio.Semaphore(2)


@tool
async def web_search(query: str) -> str:
    """Search the web for current information about a topic. Returns relevant search results with snippets."""
    return await web_search_impl(query)


@dataclass
class SectionConfig:
    name: str
    output_model: type[BaseModel]
    system_prompt_file: str
    user_prompt_file: str
    content_field: str  # "content" for SectionResult, "items" for ListSectionResult


SECTIONS: list[SectionConfig] = [
    SectionConfig(
        name="background",
        output_model=SectionResult,
        system_prompt_file="background_system.txt",
        user_prompt_file="background_user.txt",
        content_field="content",
    ),
    SectionConfig(
        name="policy_positions",
        output_model=SectionResult,
        system_prompt_file="policy_positions_system.txt",
        user_prompt_file="policy_positions_user.txt",
        content_field="content",
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
        name="recent_press",
        output_model=ListSectionResult,
        system_prompt_file="recent_press_system.txt",
        user_prompt_file="recent_press_user.txt",
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
async def research_representative(rep: Representative) -> tuple[ResearchSummary | None, UsageStats]:
    """Run 7 focused section agents concurrently, assemble into ResearchSummary."""
    total_usage = UsageStats()
    logger.info(f"Queued research for {rep.name}")
    async with _semaphore:
        logger.info(f"Starting research for {rep.name}")
        try:
            results = await asyncio.gather(
                *(run_section_agent(rep, section) for section in SECTIONS),
                return_exceptions=True,
            )

            summary_kwargs: dict = {}
            for section, result in zip(SECTIONS, results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Section '{section.name}' failed for {rep.name}: {result}",
                        exc_info=result,
                    )
                    if section.content_field == "content":
                        summary_kwargs[section.name] = ""
                    else:
                        summary_kwargs[section.name] = []
                    summary_kwargs[f"{section.name}_citations"] = []
                else:
                    content, citations, usage = result
                    summary_kwargs[section.name] = content
                    summary_kwargs[f"{section.name}_citations"] = citations
                    total_usage += usage

            logger.info(
                f"Research for {rep.name}: "
                f"{total_usage.input_tokens} in / {total_usage.output_tokens} out / "
                f"{total_usage.tool_calls} tool calls"
            )
            return ResearchSummary(**summary_kwargs), total_usage
        except Exception as e:
            logger.error(f"Research failed for {rep.name}: {e}", exc_info=True)
            return None, total_usage
