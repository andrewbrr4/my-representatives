import asyncio
import logging
import os
from pathlib import Path
from string import Template

from pydantic_ai import Agent
from pydantic_ai.settings import ModelSettings
from tavily import AsyncTavilyClient

from models import RawResearch, Representative, ResearchFinding, ResearchSummary

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_PHASE1_SYSTEM = (_PROMPTS_DIR / "research_phase1_system.txt").read_text()
_PHASE1_USER_TEMPLATE = Template((_PROMPTS_DIR / "research_user.txt").read_text())
_PHASE2_SYSTEM = (_PROMPTS_DIR / "research_phase2_system.txt").read_text()
_PHASE2_USER_TEMPLATE = Template((_PROMPTS_DIR / "research_phase2_user.txt").read_text())

# Limit concurrent research calls to avoid rate limits
_semaphore = asyncio.Semaphore(2)

# Lazy-initialized agents (deferred so .env is loaded before Anthropic client is created)
_phase1_agent: Agent[None, RawResearch] | None = None
_phase2_agent: Agent[None, ResearchSummary] | None = None


def _get_phase1_agent() -> Agent[None, RawResearch]:
    global _phase1_agent
    if _phase1_agent is None:
        _phase1_agent = Agent(
            "anthropic:claude-sonnet-4-20250514",
            output_type=RawResearch,
            instructions=_PHASE1_SYSTEM,
            retries=2,
            model_settings=ModelSettings(max_tokens=4096),
        )

        @_phase1_agent.tool_plain
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

    return _phase1_agent


def _get_phase2_agent() -> Agent[None, ResearchSummary]:
    global _phase2_agent
    if _phase2_agent is None:
        _phase2_agent = Agent(
            "anthropic:claude-sonnet-4-20250514",
            output_type=ResearchSummary,
            instructions=_PHASE2_SYSTEM,
            retries=2,
            model_settings=ModelSettings(max_tokens=2048),
        )
    return _phase2_agent


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


async def research_representative(rep: Representative) -> ResearchSummary | None:
    """Two-phase research: gather facts, then synthesize into prose with citations."""
    logger.info(f"Queued research for {rep.name}")
    async with _semaphore:
        logger.info(f"Starting research for {rep.name}")
        try:
            # Phase 1: gather raw findings
            phase1_agent = _get_phase1_agent()
            phase1_prompt = _PHASE1_USER_TEMPLATE.substitute(
                name=rep.name, office=rep.office
            )
            phase1_result = await phase1_agent.run(phase1_prompt)
            raw = phase1_result.output
            logger.info(
                f"Phase 1 complete for {rep.name}: {len(raw.findings)} findings"
            )

            if not raw.findings:
                logger.warning(f"No findings for {rep.name}, skipping Phase 2")
                return None

            # Build numbered findings block
            findings_block = _build_findings_block(raw.findings)

            # Phase 2: synthesize into structured summary
            phase2_agent = _get_phase2_agent()
            phase2_prompt = _PHASE2_USER_TEMPLATE.substitute(
                name=rep.name,
                office=rep.office,
                findings_block=findings_block,
            )
            phase2_result = await phase2_agent.run(phase2_prompt)
            output = phase2_result.output
            logger.info(
                f"Completed research for {rep.name}: "
                f"{len(output.citations)} citations, "
                f"sample text: {output.background[:100]}..."
            )
            if not output.citations:
                logger.warning(f"No citations returned for {rep.name}")
            return output
        except Exception as e:
            logger.error(f"Research failed for {rep.name}: {e}", exc_info=True)
            return None
