import asyncio
import json
import logging
import os

import anthropic
from tavily import AsyncTavilyClient

from models import Representative

logger = logging.getLogger(__name__)

# Limit concurrent Anthropic API calls to avoid rate limits
_semaphore = asyncio.Semaphore(2)

# Retry config for rate limits
_MAX_RETRIES = 8
_BASE_DELAY = 10  # seconds


async def research_representative(rep: Representative) -> str:
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
        except anthropic.RateLimitError as e:
            if attempt == _MAX_RETRIES - 1:
                raise
            delay = _BASE_DELAY * (2 ** attempt)
            logger.warning(f"Rate limited researching {rep_name}, retrying in {delay}s (attempt {attempt + 1}/{_MAX_RETRIES})")
            await asyncio.sleep(delay)


async def _research_representative_inner(rep: Representative) -> str:
    """Inner implementation with retry logic for rate limits."""
    tavily = AsyncTavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    client = anthropic.AsyncAnthropic()

    tools = [
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
        }
    ]

    system_prompt = (
        "You are a nonpartisan political research assistant. "
        "Use the web_search tool to find current information, then write your summary. "
        "Always search before writing your summary."
    )

    user_prompt = (
        f"Research {rep.name}, who serves as {rep.office}.\n"
        "Using web search, find and summarize:\n"
        "1. Their background and how long they've been in office\n"
        "2. Recent news or activity (last 6 months)\n"
        "3. Key policy positions or notable votes\n"
        "4. Any committee assignments or leadership roles\n\n"
        "Write a clear, factual, nonpartisan 2-3 paragraph summary suitable for "
        "a constituent who wants to understand who represents them."
    )

    messages = [{"role": "user", "content": user_prompt}]

    # Agentic loop: let Claude call tools as needed
    for iteration in range(8):
        logger.info(f"[{rep.name}] Agentic loop iteration {iteration + 1}")
        response = await _call_with_retry(client, system_prompt, tools, messages, rep.name)

        logger.info(f"[{rep.name}] stop_reason={response.stop_reason}, blocks={[b.type for b in response.content]}")

        if response.stop_reason == "end_turn":
            # Extract text from response
            for block in response.content:
                if block.type == "text":
                    return block.text
            return "Summary unavailable."

        # Process tool calls
        tool_results = []
        has_tool_use = False
        for block in response.content:
            if block.type == "tool_use":
                has_tool_use = True
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
                    logger.warning(f"[{rep.name}] Search failed: {e}")
                    result_text = "Search failed. Please write summary based on your existing knowledge."

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                    }
                )

        if not has_tool_use:
            # No tool use and no end_turn — extract text
            for block in response.content:
                if block.type == "text":
                    return block.text
            return "Summary unavailable."

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return "Summary unavailable — research timed out."
