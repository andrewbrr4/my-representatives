import asyncio

import routers.facts as facts_router


def test_get_facts_returns_facts(monkeypatch):
    async def fake_get_civics_facts():
        return ["A", "B", "C"]

    monkeypatch.setattr(facts_router, "get_civics_facts", fake_get_civics_facts)

    resp = asyncio.run(facts_router.get_facts())
    assert resp.facts == ["A", "B", "C"]
