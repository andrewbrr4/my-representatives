from store.interfaces import JobStoreInterface, RepCacheInterface
from store.memory import InMemoryJobStore, InMemoryRepCache

_job_store: JobStoreInterface | None = None
_rep_cache: RepCacheInterface | None = None


def get_job_store() -> JobStoreInterface:
    global _job_store
    if _job_store is None:
        _job_store = InMemoryJobStore()
    return _job_store


def get_rep_cache() -> RepCacheInterface:
    global _rep_cache
    if _rep_cache is None:
        _rep_cache = InMemoryRepCache()
    return _rep_cache
