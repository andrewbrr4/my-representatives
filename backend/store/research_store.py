import asyncio
import logging
import os
import time
from dataclasses import dataclass, field

from models import Citation, ResearchSummary

logger = logging.getLogger(__name__)

RESEARCH_TTL_SECONDS = int(os.getenv("JOB_TTL_SECONDS", "1800"))
MAX_TASKS = 1000
TOTAL_SECTIONS = 7


@dataclass
class ResearchTask:
    research_id: str
    status: str = "pending"  # "pending" | "in_progress" | "complete" | "failed"
    summary: ResearchSummary = field(default_factory=ResearchSummary)
    completed_sections: int = 0
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

    async def complete_section(
        self,
        research_id: str,
        section_name: str,
        content: str | list[str],
        citations: list[Citation],
    ) -> None:
        """Write one completed section to the task. Auto-transitions status."""
        async with self._lock:
            task = self._tasks.get(research_id)
            if not task:
                return
            object.__setattr__(task.summary, section_name, content)
            object.__setattr__(task.summary, f"{section_name}_citations", citations)
            # Re-run validator so empty content gets "Information not found."
            task.summary = ResearchSummary.model_validate(task.summary.model_dump())
            task.completed_sections += 1
            if task.status == "pending":
                task.status = "in_progress"
            if task.completed_sections >= TOTAL_SECTIONS:
                task.status = "complete"

    async def complete(self, research_id: str, summary: ResearchSummary) -> None:
        """Mark task fully complete with a complete summary (used for cache hits)."""
        async with self._lock:
            task = self._tasks.get(research_id)
            if task:
                task.status = "complete"
                task.summary = summary
                task.completed_sections = TOTAL_SECTIONS

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
