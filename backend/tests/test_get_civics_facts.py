import asyncio

import db


class _FakePool:
    def __init__(self, rows_by_call):
        # rows_by_call: list of row-lists, returned in call order
        self._rows_by_call = list(rows_by_call)
        self.calls = []  # list of (query, args)

    async def fetch(self, query, *args):
        self.calls.append((query, args))
        return self._rows_by_call.pop(0)


def _patch_pool(monkeypatch, fake):
    async def fake_get_pool():
        return fake
    monkeypatch.setattr(db, "get_pool", fake_get_pool)


def test_general_facts_when_no_issue(monkeypatch):
    fake = _FakePool([[{"text": "Gen one"}, {"text": "Gen two"}]])
    _patch_pool(monkeypatch, fake)

    result = asyncio.run(db.get_civics_facts())

    assert result == ["Gen one", "Gen two"]
    query, args = fake.calls[0]
    assert "issue_id IS NULL" in query
    assert args == ()


def test_themed_facts_when_issue_has_them(monkeypatch):
    fake = _FakePool([[{"text": "Housing fact"}]])
    _patch_pool(monkeypatch, fake)

    result = asyncio.run(db.get_civics_facts("affordable_housing"))

    assert result == ["Housing fact"]
    query, args = fake.calls[0]
    assert "issue_id = $1" in query
    assert args == ("affordable_housing",)
    assert len(fake.calls) == 1  # no fallback query


def test_falls_back_to_general_when_issue_empty(monkeypatch):
    # first call (themed) returns [], second call (general) returns rows
    fake = _FakePool([[], [{"text": "Gen fallback"}]])
    _patch_pool(monkeypatch, fake)

    result = asyncio.run(db.get_civics_facts("artificial_intelligence"))

    assert result == ["Gen fallback"]
    assert len(fake.calls) == 2
    assert "issue_id = $1" in fake.calls[0][0]
    assert "issue_id IS NULL" in fake.calls[1][0]
