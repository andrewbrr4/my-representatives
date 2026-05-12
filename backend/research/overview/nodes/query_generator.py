"""Query generator node — single LLM call producing breadth-first search queries."""

import logging
import os
from datetime import date
from pathlib import Path
from string import Template

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langfuse import observe
from langfuse.langchain import CallbackHandler
from pydantic import BaseModel, Field

from research.overview.state import V4State
from research.usage import UsageTracker

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_NUM_QUERIES = int(os.getenv("OVERVIEW_V4_NUM_QUERIES", "18"))


def _model_id() -> str:
    """Per-node model override; falls back to global ``CLAUDE_MODEL``."""
    return os.getenv("OVERVIEW_V4_QUERY_GEN_MODEL", os.environ["CLAUDE_MODEL"])


class _QueryList(BaseModel):
    queries: list[str] = Field(description="Diverse search queries, one per item.")


@observe(name="v4-query-gen")
async def query_generator(state: V4State) -> dict:
    """Single LLM call (no tools) that emits ``_NUM_QUERIES`` diverse queries."""
    rep = state["rep"]
    langfuse_handler = CallbackHandler()
    usage_tracker = UsageTracker()

    model = ChatAnthropic(
        model=_model_id(),
        max_tokens=int(os.environ["RESEARCH_MAX_TOKENS"]),
    )
    structured = model.with_structured_output(_QueryList)

    system_template = Template((_PROMPTS_DIR / "query_gen_system.txt").read_text())
    user_template = Template((_PROMPTS_DIR / "query_gen_user.txt").read_text())
    system_prompt = system_template.substitute(
        current_date=date.today().isoformat(), num_queries=str(_NUM_QUERIES)
    )
    user_prompt = user_template.substitute(
        name=rep.name, office=rep.office, num_queries=str(_NUM_QUERIES)
    )

    result = await structured.ainvoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
        config={
            "callbacks": [langfuse_handler, usage_tracker],
            "run_name": f"v4:query-gen:{rep.name}",
        },
    )
    raw_queries = [q.strip() for q in result.queries if q and q.strip()]
    # Dedupe by case/whitespace-normalized form, preserve first-seen order.
    seen: set[str] = set()
    queries: list[str] = []
    for q in raw_queries:
        key = " ".join(q.lower().split())
        if key in seen:
            continue
        seen.add(key)
        queries.append(q)
    dropped = len(raw_queries) - len(queries)
    if dropped:
        logger.info(f"[v4] query_generator: dropped {dropped} duplicate queries")
    logger.info(f"[v4] Generated {len(queries)} queries for {rep.name}")
    return {"queries": queries, "usage_log": [usage_tracker.stats]}
