import asyncio

import routers.facts as facts_router


def test_get_facts_no_issue_passes_none(monkeypatch):
    seen = {}

    async def fake_get_civics_facts(issue_id=None):
        seen["issue_id"] = issue_id
        return ["A", "B"]

    monkeypatch.setattr(facts_router, "get_civics_facts", fake_get_civics_facts)

    resp = asyncio.run(facts_router.get_facts())

    assert resp.facts == ["A", "B"]
    assert seen["issue_id"] is None


def test_get_facts_forwards_issue(monkeypatch):
    seen = {}

    async def fake_get_civics_facts(issue_id=None):
        seen["issue_id"] = issue_id
        return ["Housing"]

    monkeypatch.setattr(facts_router, "get_civics_facts", fake_get_civics_facts)

    resp = asyncio.run(facts_router.get_facts(issue="affordable_housing"))

    assert resp.facts == ["Housing"]
    assert seen["issue_id"] == "affordable_housing"
