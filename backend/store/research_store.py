import asyncio
import logging
import os
import time
from dataclasses import dataclass, field

from models import ResearchSummary

logger = logging.getLogger(__name__)

RESEARCH_TTL_SECONDS = int(os.getenv("JOB_TTL_SECONDS", "1800"))
MAX_TASKS = 1000


@dataclass
class ResearchTask:
    research_id: str
    status: str = "pending"  # "pending" | "complete" | "failed"
    summary: ResearchSummary | None = None
    created_at: float = field(default_factory=time.time)


class InMemoryResearchStore:
    def __init__(self) -> None:
        self._tasks: dict[str, ResearchTask] = {}
        self._lock = asyncio.Lock()

    async def create(self, research_id: str) -> None:
        async with self._lock:
            if len(self._tasks) >= MAX_TASKS:
                oldest_key = min(self._tasks, key=lambda k: self._tasks[k].created_at)
                del self._tasks[oldest_key]
            self._tasks[research_id] = ResearchTask(research_id=research_id)

    async def get(self, research_id: str) -> ResearchTask | None:
        async with self._lock:
            return self._tasks.get(research_id)

    async def complete(self, research_id: str, summary: ResearchSummary) -> None:
        async with self._lock:
            task = self._tasks.get(research_id)
            if task:
                task.status = "complete"
                task.summary = summary

    async def fail(self, research_id: str) -> None:
        async with self._lock:
            task = self._tasks.get(research_id)
            if task:
                task.status = "failed"

    async def cleanup(self) -> None:
        now = time.time()
        async with self._lock:
            expired = [k for k, v in self._tasks.items() if now - v.created_at > RESEARCH_TTL_SECONDS]
            for k in expired:
                del self._tasks[k]
            if expired:
                logger.info(f"Cleaned up {len(expired)} expired research tasks")
