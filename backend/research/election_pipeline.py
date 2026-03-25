"""Election research pipeline — sync context generation + async key issues research."""

import asyncio
import logging
import os
from datetime import date
from pathlib import Path
from string import Template

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents import create_agent
from langfuse.langchain import CallbackHandler

from models import Citation, ElectionResearchSummary, ListSectionResult
from research.pipeline import web_search  # reuse the same search tool
from research.usage import UsageStats, UsageTracker
from store.research_store import InMemoryResearchStore

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

_semaphore = asyncio.Semaphore(2)

ELECTION_TOTAL_SECTIONS = 2  # election_context (sync) + key_issues_and_significance (async)


async def generate_election_context(
    election_name: str,
    election_date: str,
    election_type: str,
    state: str,
) -> str:
    """Generate election type context from LLM training data. No web search needed."""
    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=512,
    )
    prompt = (
        f"In 2-3 sentences, explain what a {election_type} election is and what it means "
        f"for voters. This is the {election_name} on {election_date} in {state}. "
        f"Be concise, nonpartisan, and factual. Plain text only."
    )
    response = await model.ainvoke([HumanMessage(content=prompt)])
    return response.content


async def research_key_issues(
    election_name: str,
    election_date: str,
    election_type: str,
    state: str,
    address: str,
) -> tuple[list[str], list[Citation], UsageStats]:
    """Run one research agent with web search to find key issues and political significance."""
    langfuse_handler = CallbackHandler()
    usage_tracker = UsageTracker()
    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=int(os.environ.get("RESEARCH_MAX_TOKENS", "4096")),
    )

    system_template = Template(
        (_PROMPTS_DIR / "election_key_issues_system.txt").read_text()
    )
    user_template = Template(
        (_PROMPTS_DIR / "election_key_issues_user.txt").read_text()
    )

    system_prompt = system_template.substitute(current_date=date.today().isoformat())
    user_prompt = user_template.substitute(
        election_name=election_name,
        election_date=election_date,
        election_type=election_type,
        state=state,
        address=address,
    )

    agent = create_agent(
        model,
        tools=[web_search],
        response_format=ListSectionResult,
    )

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
            "run_name": f"election:key_issues:{election_name}",
        },
    )

    structured = result["structured_response"]
    logger.info(
        f"Key issues research complete for {election_name}: "
        f"{len(structured.citations)} citations"
    )
    return structured.items, structured.citations, usage_tracker.stats


async def research_election(
    election_name: str,
    election_date: str,
    election_type: str,
    state: str,
    address: str,
    store: InMemoryResearchStore | None = None,
    research_id: str | None = None,
) -> tuple[ElectionResearchSummary | None, UsageStats]:
    """Generate election context (sync LLM) then research key issues (async web search)."""
    total_usage = UsageStats()
    logger.info(f"Starting election research for {election_name}")

    # Step 1: Generate election context from training data (fast, no web search)
    try:
        context = await generate_election_context(
            election_name, election_date, election_type, state
        )
    except Exception as e:
        logger.error(f"Election context generation failed: {e}", exc_info=True)
        context = ""

    if store and research_id:
        await store.complete_section(research_id, "election_context", context, [])

    # Step 2: Research key issues with web search (slower)
    async with _semaphore:
        try:
            content, citations, usage = await research_key_issues(
                election_name, election_date, election_type, state, address
            )
            total_usage += usage
        except Exception as e:
            logger.error(f"Key issues research failed for {election_name}: {e}", exc_info=True)
            content = []
            citations = []

        if store and research_id:
            await store.complete_section(
                research_id, "key_issues_and_significance", content, citations
            )

    logger.info(
        f"Election research for {election_name}: "
        f"{total_usage.input_tokens} in / {total_usage.output_tokens} out / "
        f"{total_usage.tool_calls} tool calls"
    )

    if store and research_id:
        task = await store.get(research_id)
        return task.summary if task else None, total_usage

    return None, total_usage
