"""Depth subagent — focused per-topic ``create_react_agent`` with isolated state.

State (``DepthState``) is fully isolated from the parent. The subagent's
``messages`` (Tavily ToolMessage snippets, agent reasoning) live and die
in this scope. Only the structured ``search_results`` list crosses back
to the caller (the research_agent node, which tags each result with the
topic and merges them into ``depth_search_results`` on V4State).
"""

import logging
import os
from datetime import date
from pathlib import Path
from string import Template

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from research.overview.v4.state import DepthState
from research.overview.v4.tools.tavily_search import depth_tavily_search

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_DEPTH_RECURSION_LIMIT = int(os.getenv("OVERVIEW_V4_DEPTH_RECURSION_LIMIT", "8"))


def _model_id() -> str:
    """Per-node model override for the depth subagent."""
    return os.getenv("OVERVIEW_V4_DEPTH_MODEL", os.environ["CLAUDE_MODEL"])


def build_depth_agent():
    """Build a ``create_react_agent`` for depth research.

    The agent is built once per depth fanout. Compiled agents are
    stateless and could be cached at module level; we build per-run so
    the system prompt picks up today's date dynamically.
    """
    system_template = Template((_PROMPTS_DIR / "depth_agent_system.txt").read_text())
    system_prompt = system_template.substitute(current_date=date.today().isoformat())

    model = ChatAnthropic(
        model=_model_id(),
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    )
    return create_react_agent(
        model,
        tools=[depth_tavily_search],
        state_schema=DepthState,
        prompt=system_prompt,
    )


def build_depth_initial_user_message(state: DepthState) -> HumanMessage:
    """Render the depth subagent's seed user message from
    ``depth_agent_user.txt``."""
    user_template = Template((_PROMPTS_DIR / "depth_agent_user.txt").read_text())
    user_prompt = user_template.substitute(
        name=state["rep"].name,
        office=state["rep"].office,
        topic=state["topic"],
        reason=state["reason"],
    )
    return HumanMessage(content=user_prompt)


# Re-export for callers/tests.
DEPTH_RECURSION_LIMIT = _DEPTH_RECURSION_LIMIT


__all__ = ["DEPTH_RECURSION_LIMIT", "build_depth_agent", "build_depth_initial_user_message"]
