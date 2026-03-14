from abc import ABC, abstractmethod

from models import Representative, ResearchSummary


class JobStoreInterface(ABC):
    @abstractmethod
    async def create_job(self, job_id: str, representatives: list[Representative]) -> None: ...

    @abstractmethod
    async def get_job(self, job_id: str) -> dict | None: ...

    @abstractmethod
    async def update_rep_research(
        self, job_id: str, index: int, summary: ResearchSummary | None, failed: bool = False
    ) -> None: ...

    @abstractmethod
    async def mark_done(self, job_id: str) -> None: ...

    @abstractmethod
    async def mark_error(self, job_id: str, detail: str) -> None: ...

    @abstractmethod
    async def cleanup(self) -> None: ...


class RepCacheInterface(ABC):
    @abstractmethod
    async def get(self, name: str, office: str) -> ResearchSummary | None: ...

    @abstractmethod
    async def put(self, name: str, office: str, summary: ResearchSummary) -> None: ...

    @abstractmethod
    async def cleanup(self) -> None: ...
