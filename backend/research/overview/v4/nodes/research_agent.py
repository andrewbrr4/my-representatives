"""Research-agent node — a ``create_react_agent`` with a closure-bound depth tool.

The agent loops on ``messages`` until it stops calling tools. Each
``request_depth_research`` tool call writes typed ``SearchResult``
objects (tagged with the depth topic) into the agent's
``depth_search_results`` channel via ``Command(update=...)``. Only
``depth_search_results`` crosses back to ``V4State`` — the agent's
``messages`` history (breadth results in the seed prompt + tool result
acknowledgements) stays inside ``ResearchAgentState``.
"""

import logging
import os
from datetime import date
from pathlib import Path
from string import Template

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langfuse import observe
from langfuse.langchain import CallbackHandler
from langgraph.prebuilt import create_react_agent

from research.overview.v4.models import SearchResult
from research.overview.v4.state import ResearchAgentState, V4State
from research.overview.v4.tools.request_depth import make_request_depth_tool
from research.usage import UsageTracker

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_AGENT_RECURSION_LIMIT = 12
_MAX_DEPTH_CALLS = int(os.getenv("OVERVIEW_V4_AGENT_MAX_DEPTH_CALLS", "3"))


def _format_results_block(results: list[SearchResult]) -> str:
    if not results:
        return "(no results)"
    lines = []
    for i, r in enumerate(results, start=1):
        date_suffix = f"  Published: {r.published_date}\n" if r.published_date else ""
        lines.append(
            f"[{i}] {r.title}\n  URL: {r.url}\n{date_suffix}  {r.snippet}"
        )
    return "\n\n".join(lines)


@observe(name="v4-research-agent")
async def research_agent_node(state: V4State) -> dict:
    """V4State wrapper around a per-run ``create_react_agent``.

    The agent's only tool is the closure-bound ``request_depth_research``,
    so ``rep`` is captured without being exposed to the LLM. Only
    ``depth_search_results`` crosses back to V4State.
    """
    rep = state["rep"]
    filtered_results = state.get("filtered_results") or []

    system_template = Template((_PROMPTS_DIR / "research_agent_system.txt").read_text())
    user_template = Template((_PROMPTS_DIR / "research_agent_user.txt").read_text())
    system_prompt = system_template.substitute(
        current_date=date.today().isoformat(),
        max_depth_calls=str(_MAX_DEPTH_CALLS),
    )
    user_prompt = user_template.substitute(
        name=rep.name,
        office=rep.office,
        results_block=_format_results_block(filtered_results),
        max_depth_calls=str(_MAX_DEPTH_CALLS),
    )

    request_depth_tool = make_request_depth_tool(rep)
    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    )
    agent = create_react_agent(
        model,
        tools=[request_depth_tool],
        state_schema=ResearchAgentState,
        prompt=system_prompt,
    )

    langfuse_handler = CallbackHandler()
    usage_tracker = UsageTracker()

    initial: ResearchAgentState = {
        "messages": [HumanMessage(content=user_prompt)],
        "rep": rep,
        "filtered_results": filtered_results,
        "depth_search_results": [],
    }
    result = await agent.ainvoke(
        initial,
        config={
            "callbacks": [langfuse_handler, usage_tracker],
            "recursion_limit": _AGENT_RECURSION_LIMIT,
            "run_name": f"v4:research-agent:{rep.name}",
        },
    )

    depth_search_results = result.get("depth_search_results") or []
    logger.info(
        f"[v4] research_agent for {rep.name}: {len(depth_search_results)} depth results, "
        f"{usage_tracker.stats.tool_calls} depth calls"
    )
    return {"depth_search_results": depth_search_results, "usage_log": [usage_tracker.stats]}


__all__ = ["research_agent_node"]
