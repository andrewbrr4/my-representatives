import asyncio
import logging
import os
from pathlib import Path
from string import Template

import anthropic
from tavily import AsyncTavilyClient

from models import Representative, ResearchSummary

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_SYSTEM_PROMPT = (_PROMPTS_DIR / "research_system.txt").read_text()
_USER_PROMPT_TEMPLATE = Template((_PROMPTS_DIR / "research_user.txt").read_text())

# Limit concurrent Anthropic API calls to avoid rate limits
_semaphore = asyncio.Semaphore(2)

# Retry config for rate limits
_MAX_RETRIES = 8
_BASE_DELAY = 10  # seconds

_TOOLS = [
    {
        "name": "web_search",
        "description": "Search the web for current information about a topic. Returns relevant search results with snippets.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "submit_summary",
        "description": "Submit the final research summary for an elected official.",
        "input_schema": ResearchSummary.model_json_schema(),
    },
]


async def research_representative(rep: Representative) -> ResearchSummary | None:
    """Use Claude with Tavily tool use to research a representative."""
    logger.info(f"Queued research for {rep.name}")
    async with _semaphore:
        logger.info(f"Starting research for {rep.name}")
        result = await _research_representative_inner(rep)
        logger.info(f"Completed research for {rep.name}")
        return result


async def _call_with_retry(client, system_prompt, tools, messages, rep_name):
    """Call Anthropic API with exponential backoff on rate limits."""
    for attempt in range(_MAX_RETRIES):
        try:
            return await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=system_prompt,
                tools=tools,
                messages=messages,
            )
        except anthropic.RateLimitError:
            if attempt == _MAX_RETRIES - 1:
                raise
            delay = _BASE_DELAY * (2 ** attempt)
            logger.warning(f"Rate limited researching {rep_name}, retrying in {delay}s (attempt {attempt + 1}/{_MAX_RETRIES})")
            await asyncio.sleep(delay)


async def _research_representative_inner(rep: Representative) -> ResearchSummary | None:
    """Inner implementation with retry logic for rate limits."""
    tavily = AsyncTavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    client = anthropic.AsyncAnthropic()

    system_prompt = _SYSTEM_PROMPT
    user_prompt = _USER_PROMPT_TEMPLATE.substitute(name=rep.name, office=rep.office)

    messages = [{"role": "user", "content": user_prompt}]

    # Agentic loop: let Claude search, then submit structured summary
    for iteration in range(8):
        logger.info(f"[{rep.name}] Agentic loop iteration {iteration + 1}")
        response = await _call_with_retry(client, system_prompt, _TOOLS, messages, rep.name)

        logger.info(f"[{rep.name}] stop_reason={response.stop_reason}, blocks={[b.type for b in response.content]}")

        if response.stop_reason == "end_turn":
            logger.warning(f"[{rep.name}] Ended without calling submit_summary")
            return None

        # Process tool calls
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            if block.name == "submit_summary":
                logger.info(f"[{rep.name}] Received structured summary")
                return ResearchSummary(**block.input)

            if block.name == "web_search":
                query = block.input.get("query", rep.name)
                logger.info(f"[{rep.name}] Searching: {query}")
                try:
                    search_results = await tavily.search(
                        query=query, max_results=5
                    )
                    result_text = "\n\n".join(
                        f"**{r['title']}**\n{r['url']}\n{r['content']}"
                        for r in search_results.get("results", [])
                    )
                except Exception as e:
                    error_detail = str(e)
                    if hasattr(e, "response"):
                        try:
                            error_status_code = e.response.status_code
                            error_detail = e.response.text
                        except Exception:
                            pass
                    logger.warning(f"[{rep.name}] Search failed with code {error_status_code}: {error_detail}")
                    result_text = f"Search failed. Please write summary based on your existing knowledge."

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                    }
                )

        if not tool_results:
            logger.warning(f"[{rep.name}] No tool calls in response")
            return None

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    logger.warning(f"[{rep.name}] Research timed out after 8 iterations")
    return None
