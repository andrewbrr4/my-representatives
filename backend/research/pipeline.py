import asyncio
import logging
import os
from datetime import date
from pathlib import Path
from string import Template

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langfuse import observe
from langfuse.langchain import CallbackHandler
from langchain.agents import create_agent
from tavily import AsyncTavilyClient

from models import RawResearch, Representative, ResearchFinding, ResearchSummary

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_RESEARCH_SYSTEM_TEMPLATE = Template((_PROMPTS_DIR / "research_system.txt").read_text())
_RESEARCH_USER_TEMPLATE = Template((_PROMPTS_DIR / "research_user.txt").read_text())
_SUMMARY_SYSTEM = (_PROMPTS_DIR / "summary_system.txt").read_text()
_SUMMARY_USER_TEMPLATE = Template((_PROMPTS_DIR / "summary_user.txt").read_text())

# Limit concurrent research calls to avoid rate limits
_semaphore = asyncio.Semaphore(2)


@tool
async def web_search(query: str) -> str:
    """Search the web for current information about a topic. Returns relevant search results with snippets."""
    tavily = AsyncTavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    try:
        search_results = await tavily.search(query=query, max_results=5)
        return "\n\n".join(
            f"**{r['title']}**\n{r['url']}\n{r['content']}"
            for r in search_results.get("results", [])
        )
    except Exception as e:
        error_detail = str(e)
        if hasattr(e, "response"):
            try:
                error_detail = e.response.text
            except Exception:
                pass
        logger.warning(f"Search failed: {error_detail}")
        return "Search failed. Try a different query."


def _build_findings_block(findings: list[ResearchFinding]) -> str:
    """Deduplicate URLs, assign citation numbers, and format a numbered block."""
    url_to_number: dict[str, int] = {}
    lines: list[str] = []

    for finding in findings:
        url = finding.source_url
        if url not in url_to_number:
            url_to_number[url] = len(url_to_number) + 1
        num = url_to_number[url]
        lines.append(
            f"[{num}] Title: \"{finding.source_title}\" | URL: {url}\n"
            f"    Fact: {finding.fact}"
        )

    return "\n\n".join(lines)


@observe(name="research")
async def run_research_agent(rep: Representative) -> RawResearch | None:
    """Phase 1: Gather raw findings about a representative via web search agent."""
    langfuse_handler = CallbackHandler()
    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    )
    agent = create_agent(
        model,
        tools=[web_search],
        response_format=RawResearch,
    )
    system_prompt = _RESEARCH_SYSTEM_TEMPLATE.substitute(
        current_date=date.today().isoformat()
    )
    research_prompt = _RESEARCH_USER_TEMPLATE.substitute(
        name=rep.name, office=rep.office
    )
    research_result = await agent.ainvoke(
        {"messages": [
            SystemMessage(content=system_prompt),
            HumanMessage(content=research_prompt),
        ]},
        config={"callbacks": [langfuse_handler], "recursion_limit": 30},
    )
    raw = research_result["structured_response"]
    logger.info(f"Research complete for {rep.name}: {len(raw.findings)} findings")
    return raw if raw.findings else None


@observe(name="summary")
async def run_summary_chain(
    rep: Representative, findings: list[ResearchFinding]
) -> ResearchSummary:
    """Phase 2: Synthesize research findings into structured prose with citations."""
    langfuse_handler = CallbackHandler()
    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=int(os.environ["SUMMARY_MAX_TOKENS"]),
    )
    chain = model.with_structured_output(ResearchSummary)
    findings_block = _build_findings_block(findings)
    summary_prompt = _SUMMARY_USER_TEMPLATE.substitute(
        name=rep.name,
        office=rep.office,
        findings_block=findings_block,
    )
    output = await chain.ainvoke(
        [
            SystemMessage(content=_SUMMARY_SYSTEM),
            HumanMessage(content=summary_prompt),
        ],
        config={"callbacks": [langfuse_handler]},
    )
    logger.info(
        f"Summary complete for {rep.name}: "
        f"{len(output.citations)} citations, "
        f"sample text: {output.background[:100]}..."
    )
    if not output.citations:
        logger.warning(f"No citations returned for {rep.name}")
    return output


@observe(name="research-pipeline")
async def research_representative(rep: Representative) -> ResearchSummary | None:
    """Two-phase pipeline: research gathers facts, summary synthesizes prose with citations."""
    logger.info(f"Queued research for {rep.name}")
    async with _semaphore:
        logger.info(f"Starting research for {rep.name}")
        try:
            raw = await run_research_agent(rep)
            if raw is None:
                logger.warning(f"No findings for {rep.name}, skipping summary")
                return None
            return await run_summary_chain(rep, raw.findings)
        except Exception as e:
            logger.error(f"Research failed for {rep.name}: {e}", exc_info=True)
            return None
