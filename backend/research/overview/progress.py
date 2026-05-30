"""Per-node progress reporting for the v4 overview pipeline.

Single source of truth for the step -> (label, percent) mapping shown in
the frontend progress bar while research is in flight. Each node calls
``report_step(state, "<key>")`` as its first statement. The percentages are
first-draft, informed by V4_PERFORMANCE latency notes (breadth /
research_agent / formatter dominate) and are trivially tunable here.
"""

import logging

from research.overview.state import V4State

logger = logging.getLogger(__name__)

# (node_key, label shown while running, percent shown while running)
PROGRESS_STEPS: list[tuple[str, str, int]] = [
    ("query_generator", "Planning what to research", 5),
    ("breadth_search", "Searching the web", 20),
    ("filter", "Sorting through sources", 45),
    ("research_agent", "Digging into the details", 55),
    ("formatter", "Writing the summary", 85),
]

_LOOKUP: dict[str, tuple[str, int]] = {
    key: (label, pct) for key, label, pct in PROGRESS_STEPS
}


async def report_step(state: V4State, key: str) -> None:
    """Report the current pipeline step to the store, if plumbed.

    No-ops when ``store`` / ``research_id`` are absent from state (e.g. unit
    tests invoking nodes directly), so nodes can call it unconditionally.
    """
    store = state.get("store")
    research_id = state.get("research_id")
    if store is None or research_id is None:
        return
    label, pct = _LOOKUP[key]
    await store.update_progress(research_id, pct, label)
