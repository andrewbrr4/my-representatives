from abc import ABC, abstractmethod

from models import ResearchSummary


class RepCacheInterface(ABC):
    @abstractmethod
    async def get(self, name: str, office: str) -> ResearchSummary | None: ...

    @abstractmethod
    async def put(self, name: str, office: str, summary: ResearchSummary) -> None: ...

    @abstractmethod
    async def cleanup(self) -> None: ...
