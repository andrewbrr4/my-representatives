"""v1.1 overview pipeline.

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
from research.overview.v1_1.models import ResearchSummary
from research.search import web_search
from research.usage import UsageStats, UsageTracker
from store.research_store import InMemoryResearchStore

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# v1.1 owns its own semaphore — isolated from v1's.
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


@observe(name="v1_1-section-agent")
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
            "run_name": f"v1_1:{section.name}:{rep.name}",
        },
    )

    structured = result["structured_response"]
    items: list[str] = getattr(structured, section.content_field)
    citations: list[Citation] = structured.citations
    logger.info(
        f"[v1_1] Section '{section.name}' complete for {rep.name}: "
        f"{len(citations)} citations"
    )
    return items, citations, usage_tracker.stats


# research_representative is added in Task 9 (after synthesis helpers exist).
