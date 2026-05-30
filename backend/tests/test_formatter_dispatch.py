import asyncio

import research.overview.nodes.formatter as fmt


def test_dispatch_picks_streaming_when_enabled(monkeypatch):
    calls = []

    async def fake_streaming(state):
        calls.append("streaming")
        return {"summary": None, "usage_log": []}

    async def fake_structured(state):
        calls.append("structured")
        return {"summary": None, "usage_log": []}

    monkeypatch.setattr(fmt, "_streaming_enabled", lambda: True)
    monkeypatch.setattr(fmt, "_formatter_streaming", fake_streaming)
    monkeypatch.setattr(fmt, "_formatter_structured", fake_structured)

    asyncio.run(fmt.formatter({"rep": None}))
    assert calls == ["streaming"]


def test_dispatch_picks_structured_when_disabled(monkeypatch):
    calls = []

    async def fake_streaming(state):
        calls.append("streaming")
        return {"summary": None, "usage_log": []}

    async def fake_structured(state):
        calls.append("structured")
        return {"summary": None, "usage_log": []}

    monkeypatch.setattr(fmt, "_streaming_enabled", lambda: False)
    monkeypatch.setattr(fmt, "_formatter_streaming", fake_streaming)
    monkeypatch.setattr(fmt, "_formatter_structured", fake_structured)

    asyncio.run(fmt.formatter({"rep": None}))
    assert calls == ["structured"]
