import asyncio

from pydantic import BaseModel

from store.research_store import InMemoryResearchStore


class _Summary(BaseModel):
    bullets: list[str] = []


def test_update_progress_sets_fields_and_transitions():
    store = InMemoryResearchStore()

    async def run():
        await store.create("r1", total_sections=1, summary=_Summary())
        await store.update_progress("r1", 20, "Searching the web")
        return await store.get("r1")

    task = asyncio.run(run())
    assert task.progress_pct == 20
    assert task.progress_label == "Searching the web"
    assert task.status == "in_progress"  # transitioned from pending


def test_update_progress_missing_task_is_noop():
    store = InMemoryResearchStore()

    async def run():
        await store.update_progress("nope", 50, "x")  # must not raise

    asyncio.run(run())  # no exception = pass


def test_update_partial_replaces_summary_without_completing():
    store = InMemoryResearchStore()

    async def run():
        await store.create("r2", total_sections=1, summary=_Summary())
        await store.update_partial("r2", _Summary(bullets=["one"]))
        return await store.get("r2")

    task = asyncio.run(run())
    assert task.summary.bullets == ["one"]
    assert task.status == "in_progress"  # NOT complete


def test_update_partial_missing_task_is_noop():
    store = InMemoryResearchStore()

    async def run():
        await store.update_partial("nope", _Summary(bullets=["x"]))  # must not raise

    asyncio.run(run())  # no exception = pass
