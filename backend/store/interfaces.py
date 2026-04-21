from abc import ABC, abstractmethod

from models import ElectionResearchSummary, IssueStanceSummary
from research.overview import ResearchSummary


class RepCacheInterface(ABC):
    @abstractmethod
    async def get(self, name: str, office: str, version: str) -> ResearchSummary | None: ...

    @abstractmethod
    async def put(self, name: str, office: str, version: str, summary: ResearchSummary) -> None: ...

    @abstractmethod
    async def cleanup(self) -> None: ...


class ElectionCacheInterface(ABC):
    @abstractmethod
    async def get(self, election_name: str, election_date: str, ballot_hash: str) -> ElectionResearchSummary | None: ...

    @abstractmethod
    async def put(self, election_name: str, election_date: str, ballot_hash: str, summary: ElectionResearchSummary) -> None: ...

    @abstractmethod
    async def cleanup(self) -> None: ...


class IssueCacheInterface(ABC):
    @abstractmethod
    async def get(self, name: str, office: str, issue_id: str) -> IssueStanceSummary | None: ...

    @abstractmethod
    async def put(self, name: str, office: str, issue_id: str, summary: IssueStanceSummary) -> None: ...

    @abstractmethod
    async def cleanup(self) -> None: ...
