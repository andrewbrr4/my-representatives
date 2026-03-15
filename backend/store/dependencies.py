import logging
import os

from models import ResearchSummary
from store.interfaces import JobStoreInterface, RepCacheInterface
from store.memory import InMemoryJobStore

logger = logging.getLogger(__name__)

_job_store: JobStoreInterface | None = None
_rep_cache: RepCacheInterface | None = None


class NoOpRepCache(RepCacheInterface):
    """Cache that never stores or returns anything. Used when Redis is not configured."""

    async def get(self, name: str, office: str) -> ResearchSummary | None:
        return None

    async def put(self, name: str, office: str, summary: ResearchSummary) -> None:
        pass

    async def cleanup(self) -> None:
        pass


def get_job_store() -> JobStoreInterface:
    global _job_store
    if _job_store is None:
        if os.getenv("REDIS_URL"):
            from store.redis import RedisJobStore, create_redis_client

            _job_store = RedisJobStore(create_redis_client())
            logger.info("Using Redis job store")
        else:
            _job_store = InMemoryJobStore()
            logger.info("Using in-memory job store")
    return _job_store


def get_rep_cache() -> RepCacheInterface:
    global _rep_cache
    if _rep_cache is None:
        if os.getenv("REDIS_URL"):
            from store.redis import RedisRepCache, create_redis_client

            _rep_cache = RedisRepCache(create_redis_client())
            logger.info("Using Redis rep cache")
        else:
            _rep_cache = NoOpRepCache()
            logger.info("Rep cache disabled (no REDIS_URL)")
    return _rep_cache
