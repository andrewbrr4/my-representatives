import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Literal

from models import Representative, ResearchSummary
from store.interfaces import JobStoreInterface, RepCacheInterface

logger = logging.getLogger(__name__)

JOB_TTL_SECONDS = int(os.getenv("JOB_TTL_SECONDS", "1800"))
REP_CACHE_TTL_SECONDS = int(os.getenv("REP_CACHE_TTL_SECONDS", "86400"))
MAX_JOBS = 1000
MAX_CACHE_ENTRIES = 5000


@dataclass
class RepResearchState:
    status: Literal["pending", "complete", "failed"] = "pending"
    summary: ResearchSummary | None = None


@dataclass
class JobState:
    job_id: str
    status: Literal["lookup", "researching", "done", "error"] = "researching"
    created_at: float = field(default_factory=time.time)
    representatives: list[Representative] = field(default_factory=list)
    research: list[RepResearchState] = field(default_factory=list)
    error_detail: str | None = None


def _cache_key(name: str, office: str) -> str:
    return f"{name.lower().strip()}|{office.lower().strip()}"


class InMemoryJobStore(JobStoreInterface):
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._lock = asyncio.Lock()

    async def create_job(self, job_id: str, representatives: list[Representative]) -> None:
        async with self._lock:
            # Enforce cap
            if len(self._jobs) >= MAX_JOBS:
                oldest_key = min(self._jobs, key=lambda k: self._jobs[k].created_at)
                del self._jobs[oldest_key]
            self._jobs[job_id] = JobState(
                job_id=job_id,
                representatives=representatives,
                research=[RepResearchState() for _ in representatives],
            )

    async def get_job(self, job_id: str) -> dict | None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return {
                "job_id": job.job_id,
                "status": job.status,
                "representatives": [r.model_dump() for r in job.representatives],
                "research": [
                    {"index": i, "status": rs.status, "summary": rs.summary.model_dump() if rs.summary else None}
                    for i, rs in enumerate(job.research)
                ],
                "error_detail": job.error_detail,
            }

    async def update_rep_research(
        self, job_id: str, index: int, summary: ResearchSummary | None, failed: bool = False
    ) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            if 0 <= index < len(job.research):
                job.research[index].status = "failed" if failed else "complete"
                job.research[index].summary = summary

    async def mark_done(self, job_id: str) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "done"

    async def mark_error(self, job_id: str, detail: str) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "error"
                job.error_detail = detail

    async def cleanup(self) -> None:
        now = time.time()
        async with self._lock:
            expired = [k for k, v in self._jobs.items() if now - v.created_at > JOB_TTL_SECONDS]
            for k in expired:
                del self._jobs[k]
            if expired:
                logger.info(f"Cleaned up {len(expired)} expired jobs")


class InMemoryRepCache(RepCacheInterface):
    def __init__(self) -> None:
        self._cache: dict[str, tuple[ResearchSummary, float]] = {}
        self._lock = asyncio.Lock()

    async def get(self, name: str, office: str) -> ResearchSummary | None:
        key = _cache_key(name, office)
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            summary, ts = entry
            if time.time() - ts > REP_CACHE_TTL_SECONDS:
                del self._cache[key]
                return None
            logger.info(f"Cache hit for {name} ({office})")
            return summary

    async def put(self, name: str, office: str, summary: ResearchSummary) -> None:
        key = _cache_key(name, office)
        async with self._lock:
            if len(self._cache) >= MAX_CACHE_ENTRIES:
                oldest_key = min(self._cache, key=lambda k: self._cache[k][1])
                del self._cache[oldest_key]
            self._cache[key] = (summary, time.time())

    async def cleanup(self) -> None:
        now = time.time()
        async with self._lock:
            expired = [k for k, (_, ts) in self._cache.items() if now - ts > REP_CACHE_TTL_SECONDS]
            for k in expired:
                del self._cache[k]
            if expired:
                logger.info(f"Cleaned up {len(expired)} expired cache entries")
