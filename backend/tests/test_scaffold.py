def test_imports_bare_module():
    from store.research_store import InMemoryResearchStore

    assert InMemoryResearchStore is not None
