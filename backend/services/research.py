import asyncio
import logging
import os
from pathlib import Path
from string import Template

from pydantic_ai import Agent
from pydantic_ai.settings import ModelSettings
from tavily import AsyncTavilyClient

from models import Representative, ResearchSummary

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_SYSTEM_PROMPT = (_PROMPTS_DIR / "research_system.txt").read_text()
_USER_PROMPT_TEMPLATE = Template((_PROMPTS_DIR / "research_user.txt").read_text())

# Limit concurrent research calls to avoid rate limits
_semaphore = asyncio.Semaphore(2)

# Lazy-initialized agent (deferred so .env is loaded before Anthropic client is created)
_agent: Agent[None, ResearchSummary] | None = None


def _get_agent() -> Agent[None, ResearchSummary]:
    global _agent
    if _agent is None:
        _agent = Agent(
            "anthropic:claude-sonnet-4-20250514",
            output_type=ResearchSummary,
            instructions=_SYSTEM_PROMPT,
            retries=2,
            model_settings=ModelSettings(max_tokens=1024),
        )

        @_agent.tool_plain
        async def web_search(query: str) -> str:
            """Search the web for current information about a topic. Returns relevant search results with snippets."""
            tavily = AsyncTavilyClient(api_key=os.environ["TAVILY_API_KEY"])
            print(os.environ["TAVILY_API_KEY"])
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
                return "Search failed. Please write summary based on your existing knowledge."

    return _agent


async def research_representative(rep: Representative) -> ResearchSummary | None:
    """Use PydanticAI agent with Tavily web search to research a representative."""
    logger.info(f"Queued research for {rep.name}")
    async with _semaphore:
        logger.info(f"Starting research for {rep.name}")
        try:
            agent = _get_agent()
            user_prompt = _USER_PROMPT_TEMPLATE.substitute(name=rep.name, office=rep.office)
            result = await agent.run(user_prompt)
            logger.info(f"Completed research for {rep.name}")
            return result.output
        except Exception as e:
            logger.error(f"Research failed for {rep.name}: {e}")
            return None
