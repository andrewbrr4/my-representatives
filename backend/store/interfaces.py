from abc import ABC, abstractmethod

from models import ElectionResearchSummary, ResearchSummary


class RepCacheInterface(ABC):
    @abstractmethod
    async def get(self, name: str, office: str) -> ResearchSummary | None: ...

    @abstractmethod
    async def put(self, name: str, office: str, summary: ResearchSummary) -> None: ...

    @abstractmethod
    async def cleanup(self) -> None: ...


class ElectionCacheInterface(ABC):
    @abstractmethod
    async def get(self, election_name: str, election_date: str, address_hash: str) -> ElectionResearchSummary | None: ...

    @abstractmethod
    async def put(self, election_name: str, election_date: str, address_hash: str, summary: ElectionResearchSummary) -> None: ...

    @abstractmethod
    async def cleanup(self) -> None: ...
