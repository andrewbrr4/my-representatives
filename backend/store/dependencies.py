import logging
import os

from models import ElectionResearchSummary, ResearchSummary
from store.interfaces import ElectionCacheInterface, RepCacheInterface
from store.research_store import InMemoryResearchStore

logger = logging.getLogger(__name__)

_rep_cache: RepCacheInterface | None = None
_research_store: InMemoryResearchStore | None = None
_election_cache: ElectionCacheInterface | None = None


class NoOpRepCache(RepCacheInterface):
    """Cache that never stores or returns anything. Used when Redis is not configured."""

    async def get(self, name: str, office: str) -> ResearchSummary | None:
        return None

    async def put(self, name: str, office: str, summary: ResearchSummary) -> None:
        pass

    async def cleanup(self) -> None:
        pass


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


class NoOpElectionCache(ElectionCacheInterface):
    async def get(self, election_name: str, election_date: str, address_hash: str) -> ElectionResearchSummary | None:
        return None

    async def put(self, election_name: str, election_date: str, address_hash: str, summary: ElectionResearchSummary) -> None:
        pass

    async def cleanup(self) -> None:
        pass


def get_election_cache() -> ElectionCacheInterface:
    global _election_cache
    if _election_cache is None:
        if os.getenv("REDIS_URL"):
            from store.redis import RedisElectionCache, create_redis_client
            _election_cache = RedisElectionCache(create_redis_client())
            logger.info("Using Redis election cache")
        else:
            _election_cache = NoOpElectionCache()
            logger.info("Election cache disabled (no REDIS_URL)")
    return _election_cache


def get_research_store() -> InMemoryResearchStore:
    global _research_store
    if _research_store is None:
        _research_store = InMemoryResearchStore()
        logger.info("Using in-memory research store")
    return _research_store
