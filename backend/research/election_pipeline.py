"""Election research pipeline — single LLM call to generate a ballot overview paragraph."""

import logging
import os
from pathlib import Path
from string import Template

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from models import BallotMeasure, Contest, ElectionResearchSummary
from research.usage import UsageStats, UsageTracker
from store.research_store import InMemoryResearchStore

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_BALLOT_OVERVIEW_TEMPLATE = Template((_PROMPTS_DIR / "election_ballot_overview.txt").read_text())

logger = logging.getLogger(__name__)

ELECTION_TOTAL_SECTIONS = 1  # ballot_overview only


def _build_ballot_context(contests: list[Contest], ballot_measures: list[BallotMeasure]) -> str:
    """Build a text description of what's on the ballot for the LLM prompt."""
    parts: list[str] = []

    if contests:
        parts.append("CONTESTS:")
        for c in contests:
            candidates = ", ".join(
                f"{cand.name} ({cand.party or 'no party'})" for cand in c.candidates
            ) or "candidates not listed"
            parts.append(f"  - {c.office} ({c.level}): {candidates}")

    if ballot_measures:
        parts.append("BALLOT MEASURES / REFERENDA:")
        for m in ballot_measures:
            scope = f" ({m.district_scope})" if m.district_scope else ""
            parts.append(f"  - {m.title}{scope}: {m.description}")
            if m.responses:
                parts.append(f"    Voter options: {', '.join(m.responses)}")

    if not parts:
        parts.append("No specific contest or ballot measure details available.")

    return "\n".join(parts)


async def generate_ballot_overview(
    election_name: str,
    election_date: str,
    election_type: str,
    state: str,
    contests: list[Contest],
    ballot_measures: list[BallotMeasure],
) -> tuple[str, UsageStats]:
    """Generate a single conversational paragraph explaining what's on the ballot."""
    usage_tracker = UsageTracker()
    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=512,
    )

    ballot_context = _build_ballot_context(contests, ballot_measures)

    prompt = _BALLOT_OVERVIEW_TEMPLATE.substitute(
        election_name=election_name,
        election_date=election_date,
        election_type=election_type,
        state=state,
        ballot_context=ballot_context,
    )

    response = await model.ainvoke(
        [HumanMessage(content=prompt)],
        config={"callbacks": [usage_tracker]},
    )
    return response.content, usage_tracker.stats


async def research_election(
    election_name: str,
    election_date: str,
    election_type: str,
    state: str,
    address: str,
    contests: list[Contest] | None = None,
    ballot_measures: list[BallotMeasure] | None = None,
    store: InMemoryResearchStore | None = None,
    research_id: str | None = None,
) -> tuple[ElectionResearchSummary | None, UsageStats]:
    """Generate a ballot overview paragraph for the election."""
    logger.info(f"Starting election research for {election_name}")

    try:
        overview, usage = await generate_ballot_overview(
            election_name, election_date, election_type, state,
            contests or [], ballot_measures or [],
        )
    except Exception as e:
        logger.error(f"Ballot overview generation failed: {e}", exc_info=True)
        usage = UsageStats()
        if store and research_id:
            await store.fail(research_id)
            task = await store.get(research_id)
            return task.summary if task else None, usage
        return None, usage

    if store and research_id:
        await store.complete_section(research_id, "ballot_overview", overview, [])

    logger.info(
        f"Election research for {election_name}: "
        f"{usage.input_tokens} in / {usage.output_tokens} out / "
        f"{usage.tool_calls} tool calls"
    )

    if store and research_id:
        task = await store.get(research_id)
        return task.summary if task else None, usage

    return None, usage
