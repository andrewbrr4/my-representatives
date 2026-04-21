import logging
import os

import redis.asyncio as redis

from models import ElectionResearchSummary, IssueStanceSummary
from research.overview import ResearchSummary
from store.interfaces import ElectionCacheInterface, IssueCacheInterface, RepCacheInterface

logger = logging.getLogger(__name__)

REP_CACHE_TTL_SECONDS = int(os.getenv("REP_CACHE_TTL_SECONDS", "259200"))


def create_redis_client() -> redis.Redis:
    url = os.environ["REDIS_URL"]
    logger.info(f"Connecting to Redis at {url}")
    return redis.from_url(url, decode_responses=True)


def _cache_key(name: str, office: str, version: str) -> str:
    return f"repcache:{version}:{name.lower().strip()}|{office.lower().strip()}"


class RedisRepCache(RepCacheInterface):
    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    async def get(self, name: str, office: str, version: str) -> ResearchSummary | None:
        key = _cache_key(name, office, version)
        try:
            data = await self._r.get(key)
        except Exception as e:
            logger.error(f"Redis GET failed for {name} ({office}) [{version}]: {e}")
            return None
        if data is None:
            logger.debug(f"Cache miss for {name} ({office}) [{version}]")
            return None
        logger.info(f"Cache hit for {name} ({office}) [{version}]")
        return ResearchSummary.model_validate_json(data)

    async def put(self, name: str, office: str, version: str, summary: ResearchSummary) -> None:
        key = _cache_key(name, office, version)
        try:
            await self._r.set(key, summary.model_dump_json(), ex=REP_CACHE_TTL_SECONDS)
            logger.info(f"Cached research for {name} ({office}) [{version}], TTL={REP_CACHE_TTL_SECONDS}s")
        except Exception as e:
            logger.error(f"Redis SET failed for {name} ({office}) [{version}]: {e}")

    async def cleanup(self) -> None:
        pass


def _election_cache_key(election_name: str, election_date: str, ballot_hash: str) -> str:
    return f"electioncache:{election_name.lower().strip()}|{election_date}|{ballot_hash}"


class RedisElectionCache(ElectionCacheInterface):
    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    async def get(self, election_name: str, election_date: str, ballot_hash: str) -> ElectionResearchSummary | None:
        key = _election_cache_key(election_name, election_date, ballot_hash)
        try:
            data = await self._r.get(key)
        except Exception as e:
            logger.error(f"Redis GET failed for election {election_name}: {e}")
            return None
        if data is None:
            return None
        return ElectionResearchSummary.model_validate_json(data)

    async def put(self, election_name: str, election_date: str, ballot_hash: str, summary: ElectionResearchSummary) -> None:
        key = _election_cache_key(election_name, election_date, ballot_hash)
        try:
            await self._r.set(key, summary.model_dump_json(), ex=REP_CACHE_TTL_SECONDS)
        except Exception as e:
            logger.error(f"Redis SET failed for election {election_name}: {e}")

    async def cleanup(self) -> None:
        pass


def _issue_cache_key(name: str, office: str, issue_id: str) -> str:
    return f"issuecache:{name.lower().strip()}|{office.lower().strip()}|{issue_id.lower().strip()}"


class RedisIssueCache(IssueCacheInterface):
    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    async def get(self, name: str, office: str, issue_id: str) -> IssueStanceSummary | None:
        key = _issue_cache_key(name, office, issue_id)
        try:
            data = await self._r.get(key)
        except Exception as e:
            logger.error(f"Redis GET failed for issue {name}/{issue_id}: {e}")
            return None
        if data is None:
            return None
        return IssueStanceSummary.model_validate_json(data)

    async def put(self, name: str, office: str, issue_id: str, summary: IssueStanceSummary) -> None:
        key = _issue_cache_key(name, office, issue_id)
        try:
            await self._r.set(key, summary.model_dump_json(), ex=REP_CACHE_TTL_SECONDS)
        except Exception as e:
            logger.error(f"Redis SET failed for issue {name}/{issue_id}: {e}")

    async def cleanup(self) -> None:
        pass
