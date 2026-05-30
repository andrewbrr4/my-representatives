import asyncio

import db


class _FakePool:
    def __init__(self, rows):
        self._rows = rows
        self.last_query = None

    async def fetch(self, query):
        self.last_query = query
        return self._rows


def test_get_civics_facts_returns_text_list(monkeypatch):
    fake = _FakePool([{"text": "Fact one"}, {"text": "Fact two"}])

    async def fake_get_pool():
        return fake

    monkeypatch.setattr(db, "get_pool", fake_get_pool)

    result = asyncio.run(db.get_civics_facts())
    assert result == ["Fact one", "Fact two"]
    assert "WHERE active" in fake.last_query
