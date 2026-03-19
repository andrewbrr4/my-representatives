import logging
import os

import redis.asyncio as redis

from models import ResearchSummary
from store.interfaces import RepCacheInterface

logger = logging.getLogger(__name__)

REP_CACHE_TTL_SECONDS = int(os.getenv("REP_CACHE_TTL_SECONDS", "86400"))


def create_redis_client() -> redis.Redis:
    url = os.environ["REDIS_URL"]
    logger.info(f"Connecting to Redis at {url}")
    return redis.from_url(url, decode_responses=True)


def _cache_key(name: str, office: str) -> str:
    return f"repcache:{name.lower().strip()}|{office.lower().strip()}"


class RedisRepCache(RepCacheInterface):
    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    async def get(self, name: str, office: str) -> ResearchSummary | None:
        key = _cache_key(name, office)
        try:
            data = await self._r.get(key)
        except Exception as e:
            logger.error(f"Redis GET failed for {name} ({office}): {e}")
            return None
        if data is None:
            logger.debug(f"Cache miss for {name} ({office})")
            return None
        logger.info(f"Cache hit for {name} ({office})")
        return ResearchSummary.model_validate_json(data)

    async def put(self, name: str, office: str, summary: ResearchSummary) -> None:
        key = _cache_key(name, office)
        try:
            await self._r.set(key, summary.model_dump_json(), ex=REP_CACHE_TTL_SECONDS)
            logger.info(f"Cached research for {name} ({office}), TTL={REP_CACHE_TTL_SECONDS}s")
        except Exception as e:
            logger.error(f"Redis SET failed for {name} ({office}): {e}")

    async def cleanup(self) -> None:
        # Redis handles TTL-based expiry automatically.
        pass
