import asyncio

from pydantic import BaseModel

from research.overview.progress import PROGRESS_STEPS, report_step
from store.research_store import InMemoryResearchStore


class _Summary(BaseModel):
    bullets: list[str] = []


def test_report_step_writes_label_and_pct():
    store = InMemoryResearchStore()

    async def run():
        await store.create("r1", total_sections=1, summary=_Summary())
        await report_step({"store": store, "research_id": "r1"}, "breadth_search")
        return await store.get("r1")

    task = asyncio.run(run())
    assert task.progress_label == "Searching the web"
    assert task.progress_pct == 20


def test_report_step_noops_without_store():
    async def run():
        # No store / research_id in state -> must not raise.
        await report_step({}, "breadth_search")

    asyncio.run(run())


def test_all_pipeline_node_keys_present():
    keys = {key for key, _label, _pct in PROGRESS_STEPS}
    assert keys == {
        "query_generator",
        "breadth_search",
        "filter",
        "research_agent",
        "formatter",
    }
