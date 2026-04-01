"""Issue stance research — normalize user queries and research rep stances."""

import asyncio
import logging
import os
from datetime import date
from pathlib import Path
from string import Template

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents import create_agent
from langfuse import observe
from langfuse.langchain import CallbackHandler
from pydantic import BaseModel

from db import get_issues_taxonomy
from models import Citation, IssueInfo, ListSectionResult, Representative
from research.pipeline import web_search  # reuse the same search tool
from research.usage import UsageStats, UsageTracker
from store.research_store import InMemoryResearchStore

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_MATCH_SYSTEM_TEMPLATE = Template((_PROMPTS_DIR / "issue_match_system.txt").read_text())
_STANCE_SYSTEM_TEMPLATE = Template((_PROMPTS_DIR / "issue_stance_system.txt").read_text())
_STANCE_USER_TEMPLATE = Template((_PROMPTS_DIR / "issue_stance_user.txt").read_text())

_semaphore = asyncio.Semaphore(2)

ISSUE_TOTAL_SECTIONS = 1

_REJECTION_MESSAGE = (
    "We couldn't match that to a political issue. "
    "Try something like 'gun control' or 'immigration'."
)


class IssueMatchResult(BaseModel):
    """Structured output from the issue classifier LLM."""
    matched: bool
    issue_id: str | None = None
    issue_label: str | None = None
    novel: bool = False


async def match_issue(query: str) -> tuple[bool, IssueInfo | None, bool]:
    """Classify user input against the issues taxonomy.

    Returns (matched, IssueInfo or None, novel).
    """
    taxonomy = await get_issues_taxonomy()
    issues_list = "\n".join(f"- {row['id']}: {row['label']}" for row in taxonomy)

    system_prompt = _MATCH_SYSTEM_TEMPLATE.substitute(
        current_date=date.today().isoformat(),
        issues_list=issues_list,
    )

    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=256,
    )
    result = model.with_structured_output(IssueMatchResult)

    response = await result.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=query),
    ])

    if response.matched and response.issue_id and response.issue_label:
        return True, IssueInfo(id=response.issue_id, label=response.issue_label), response.novel
    return False, None, False


@observe(name="issue-stance-agent")
async def research_issue_stance(
    rep: Representative,
    issue_label: str,
    store: InMemoryResearchStore | None = None,
    research_id: str | None = None,
) -> tuple[list[str] | None, list[Citation], UsageStats]:
    """Run one research agent to find a rep's stance on a specific issue."""
    langfuse_handler = CallbackHandler()
    usage_tracker = UsageTracker()
    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=int(os.environ.get("RESEARCH_MAX_TOKENS", "4096")),
    )

    system_prompt = _STANCE_SYSTEM_TEMPLATE.substitute(
        current_date=date.today().isoformat()
    )
    user_prompt = _STANCE_USER_TEMPLATE.substitute(
        name=rep.name,
        office=rep.office,
        issue_label=issue_label,
    )

    agent = create_agent(
        model,
        tools=[web_search],
        response_format=ListSectionResult,
    )

    async with _semaphore:
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
                "run_name": f"issue:{rep.name}:{issue_label}",
            },
        )

    structured = result["structured_response"]
    items = structured.items
    citations = structured.citations

    if store and research_id:
        await store.complete_section(research_id, "stance_summary", items, citations)

    logger.info(
        f"Issue stance research complete for {rep.name} on {issue_label}: "
        f"{len(citations)} citations"
    )
    return items, citations, usage_tracker.stats
