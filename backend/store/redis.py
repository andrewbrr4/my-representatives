import json
import logging
import os

import redis.asyncio as redis

from models import Representative, ResearchSummary
from store.interfaces import JobStoreInterface, RepCacheInterface

logger = logging.getLogger(__name__)

JOB_TTL_SECONDS = int(os.getenv("JOB_TTL_SECONDS", "1800"))
REP_CACHE_TTL_SECONDS = int(os.getenv("REP_CACHE_TTL_SECONDS", "86400"))


def create_redis_client() -> redis.Redis:
    url = os.environ["REDIS_URL"]
    return redis.from_url(url, decode_responses=True)


def _cache_key(name: str, office: str) -> str:
    return f"repcache:{name.lower().strip()}|{office.lower().strip()}"


def _job_key(job_id: str) -> str:
    return f"job:{job_id}"


class RedisRepCache(RepCacheInterface):
    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    async def get(self, name: str, office: str) -> ResearchSummary | None:
        key = _cache_key(name, office)
        data = await self._r.get(key)
        if data is None:
            return None
        logger.info(f"Cache hit for {name} ({office})")
        return ResearchSummary.model_validate_json(data)

    async def put(self, name: str, office: str, summary: ResearchSummary) -> None:
        key = _cache_key(name, office)
        await self._r.set(key, summary.model_dump_json(), ex=REP_CACHE_TTL_SECONDS)

    async def cleanup(self) -> None:
        # Redis handles TTL-based expiry automatically.
        pass


class RedisJobStore(JobStoreInterface):
    """Redis-backed job store.

    Each job is stored as a Redis hash with fields:
      - status: str
      - error_detail: str | ""
      - representatives: JSON array
      - research:{index}: JSON object {"status": ..., "summary": ...}
    """

    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    async def create_job(self, job_id: str, representatives: list[Representative]) -> None:
        key = _job_key(job_id)
        pipe = self._r.pipeline()
        pipe.hset(key, "status", "researching")
        pipe.hset(key, "error_detail", "")
        pipe.hset(
            key,
            "representatives",
            json.dumps([r.model_dump() for r in representatives]),
        )
        for i in range(len(representatives)):
            pipe.hset(key, f"research:{i}", json.dumps({"status": "pending", "summary": None}))
        pipe.expire(key, JOB_TTL_SECONDS)
        await pipe.execute()

    async def get_job(self, job_id: str) -> dict | None:
        key = _job_key(job_id)
        data = await self._r.hgetall(key)
        if not data:
            return None

        representatives = json.loads(data["representatives"])
        research = []
        for i in range(len(representatives)):
            r_data = data.get(f"research:{i}")
            if r_data:
                parsed = json.loads(r_data)
                research.append({"index": i, **parsed})
            else:
                research.append({"index": i, "status": "pending", "summary": None})

        return {
            "job_id": job_id,
            "status": data.get("status", "researching"),
            "representatives": representatives,
            "research": research,
            "error_detail": data.get("error_detail") or None,
        }

    async def update_rep_research(
        self, job_id: str, index: int, summary: ResearchSummary | None, failed: bool = False
    ) -> None:
        key = _job_key(job_id)
        r_data = {
            "status": "failed" if failed else "complete",
            "summary": summary.model_dump() if summary else None,
        }
        await self._r.hset(key, f"research:{index}", json.dumps(r_data))

    async def mark_done(self, job_id: str) -> None:
        await self._r.hset(_job_key(job_id), "status", "done")

    async def mark_error(self, job_id: str, detail: str) -> None:
        key = _job_key(job_id)
        pipe = self._r.pipeline()
        pipe.hset(key, "status", "error")
        pipe.hset(key, "error_detail", detail)
        await pipe.execute()

    async def cleanup(self) -> None:
        # Redis handles TTL-based expiry automatically.
        pass
