# Upcoming Elections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "Upcoming Elections" tab where users see elections, contests, candidates (with reusable research), and auto-generated election context — all from the same address lookup.

**Architecture:** Lazy-load elections as an independent feature. New `services/elections.py` calls Google Civic API. New election research pipeline (3 sections) runs automatically. Candidates reuse existing `POST /api/research`. React Router added for `/reps` and `/elections` tabs. `InMemoryResearchStore` parameterized for variable section counts.

**Tech Stack:** FastAPI, React 19, React Router v7, TypeScript, Tailwind v4, shadcn/ui, Google Civic Information API v2, LangChain, Tavily

**Spec:** `docs/superpowers/specs/2026-03-24-upcoming-elections-design.md`

---

## File Structure

### Backend — New Files
| File | Responsibility |
|------|---------------|
| `backend/models.py` (modify) | Add `Candidate`, `Contest`, `PollingLocation`, `Election`, `ElectionsResponse`, `ElectionResearchSummary`, `ElectionResearchRequest`, `ElectionResearchResponse` |
| `backend/services/elections.py` (create) | Google Civic API client — fetches elections, contests, candidates for an address |
| `backend/routers/elections.py` (create) | `POST /api/elections` endpoint + `POST /api/election-research` + `GET /api/election-research/{id}` |
| `backend/research/election_pipeline.py` (create) | Election research: 1 sync LLM call (context) + 1 web search agent (key issues) |
| `backend/research/prompts/election_key_issues_system.txt` (create) | System prompt for key issues agent |
| `backend/research/prompts/election_key_issues_user.txt` (create) | User prompt for key issues agent |
| `backend/store/interfaces.py` (modify) | Add `ElectionCacheInterface` ABC |
| `backend/store/research_store.py` (modify) | Parameterize `TOTAL_SECTIONS` → per-task `total_sections` |
| `backend/store/redis.py` (modify) | Add `RedisElectionCache` |
| `backend/store/dependencies.py` (modify) | Add `get_election_cache()` singleton |
| `backend/main.py` (modify) | Register elections router, add election cache cleanup |
| `backend/db.py` (modify) | Add `task_type` param to `save_research_task()` |
| `backend/migrations/002_add_task_type_to_research_tasks.sql` (create) | Add `task_type` column |

### Frontend — New Files
| File | Responsibility |
|------|---------------|
| `frontend/src/main.tsx` (modify) | Wrap app in `BrowserRouter` |
| `frontend/src/App.tsx` (rewrite) | Router setup with routes for `/`, `/reps`, `/elections` |
| `frontend/src/contexts/AddressContext.tsx` (create) | Shared address state across routes |
| `frontend/src/pages/SearchPage.tsx` (create) | Landing page — address input + welcome message |
| `frontend/src/pages/RepresentativesPage.tsx` (create) | Existing rep results (extracted from App.tsx) |
| `frontend/src/pages/ElectionsPage.tsx` (create) | Elections tab — election cards, contests, candidates |
| `frontend/src/components/TabNav.tsx` (create) | Tab bar navigation between /reps and /elections |
| `frontend/src/components/ElectionCard.tsx` (create) | Single election card — header, AI context, polling, contests |
| `frontend/src/components/CandidateCard.tsx` (create) | Compact candidate card — reuses RepCard patterns |
| `frontend/src/hooks/useElections.ts` (create) | Fetches `POST /api/elections` on mount |
| `frontend/src/hooks/useElectionResearch.ts` (create) | Polls election research progress |
| `frontend/src/types/index.ts` (modify) | Add election TypeScript interfaces |

---

## Task 1: Backend Data Models

**Files:**
- Modify: `backend/models.py:71-91`
- Modify: `backend/migrations/002_add_task_type_to_research_tasks.sql` (create)

- [ ] **Step 1: Add election models to `backend/models.py`**

Add after `RepresentativesResponse` (line 81):

```python
class PollingLocation(BaseModel):
    name: str
    address: str
    hours: str | None = None


class Candidate(BaseModel):
    name: str
    office: str
    level: str  # "federal" | "state" | "municipal"
    party: str | None = None
    photo_url: str | None = None
    contest_name: str = ""
    incumbent: bool = False

    def to_representative(self) -> "Representative":
        """Convert to Representative shape for the research endpoint."""
        return Representative(
            name=self.name,
            office=self.office,
            level=self.level,
            party=self.party,
            photo_url=self.photo_url,
        )


class Contest(BaseModel):
    office: str
    level: str  # "federal" | "state" | "municipal"
    district_name: str | None = None
    candidates: list[Candidate] = []


class VoterInfo(BaseModel):
    """Parsed from Google Civic API state[].electionAdministrationBody. No research needed."""
    registration_url: str | None = None
    absentee_url: str | None = None
    ballot_info_url: str | None = None
    polling_location_url: str | None = None
    early_vote_sites: list[PollingLocation] = []
    drop_off_locations: list[PollingLocation] = []
    mail_only: bool = False
    admin_body_name: str | None = None
    admin_body_url: str | None = None


class Election(BaseModel):
    name: str
    date: str  # ISO format
    election_type: str  # "primary" | "general" | "runoff"
    polling_location: PollingLocation | None = None
    voter_info: VoterInfo | None = None
    contests: list[Contest] = []


class ElectionsResponse(BaseModel):
    elections: list[Election]
    research_ids: dict[str, str] = Field(default_factory=dict)  # key: "election_name|date" → research_id


class ElectionResearchSummary(BaseModel):
    """Two sections: election_context (sync LLM, no search) + key_issues_and_significance (async, web search)."""
    election_context: str | None = None
    key_issues_and_significance: str | None = None
    citations: list[Citation] = Field(default_factory=list)

    SECTION_NAMES: list[str] = Field(default=[
        "election_context", "key_issues_and_significance",
    ], exclude=True)


class ElectionResearchRequest(BaseModel):
    election_name: str
    election_date: str
    election_type: str
    state: str
    address: str


class ElectionResearchResponse(BaseModel):
    research_id: str
    status: Literal["pending", "in_progress", "complete", "failed"]
    summary: ElectionResearchSummary | None = None
```

- [ ] **Step 2: Create migration for `task_type` column**

Create `backend/migrations/002_add_task_type_to_research_tasks.sql`:

```sql
-- 002: Add task_type column to research_tasks for distinguishing rep vs election research.
ALTER TABLE research_tasks ADD COLUMN task_type text NOT NULL DEFAULT 'rep';
```

- [ ] **Step 3: Verify models import cleanly**

Run: `cd backend && python -c "from models import Candidate, Contest, Election, ElectionsResponse, ElectionResearchSummary, ElectionResearchRequest, ElectionResearchResponse; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/models.py backend/migrations/002_add_task_type_to_research_tasks.sql
git commit -m "feat: add election data models and task_type migration"
```

---

## Task 2: Parameterize InMemoryResearchStore

**Files:**
- Modify: `backend/store/research_store.py:13-70`

The store currently hardcodes `TOTAL_SECTIONS = 7`. We need per-task section counts so election research (3 sections) knows when it's complete.

- [ ] **Step 1: Update `ResearchTask` dataclass to include `total_sections` and use generic summary type**

In `backend/store/research_store.py`:
- Remove the `TOTAL_SECTIONS = 7` constant
- Update imports: add `from pydantic import BaseModel`
- Update `ResearchTask`:

```python
from pydantic import BaseModel as PydanticBaseModel

@dataclass
class ResearchTask:
    research_id: str
    total_sections: int = 7  # default for rep research
    status: str = "pending"
    summary: PydanticBaseModel = field(default_factory=ResearchSummary)
    completed_sections: int = 0
    created_at: float = field(default_factory=time.time)
```

- [ ] **Step 2: Update `create()` to accept `total_sections` and a generic summary**

```python
async def create(self, research_id: str, total_sections: int = 7, summary: PydanticBaseModel | None = None) -> None:
    async with self._lock:
        if len(self._tasks) >= MAX_TASKS:
            oldest_key = min(self._tasks, key=lambda k: self._tasks[k].created_at)
            del self._tasks[oldest_key]
        task = ResearchTask(research_id=research_id, total_sections=total_sections)
        if summary is not None:
            task.summary = summary
        self._tasks[research_id] = task
```

- [ ] **Step 3: Update `complete_section()` to be model-agnostic**

The current code hardcodes `ResearchSummary.model_validate()` and assumes per-section citation fields like `{section}_citations`. For `ElectionResearchSummary`, citations are aggregated into a flat `citations` list and there are no per-section citation fields.

Replace the entire `complete_section` method:

```python
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
        summary = task.summary
        object.__setattr__(summary, section_name, content)
        # Per-section citations (RepResearchSummary) vs flat citations (ElectionResearchSummary)
        if hasattr(summary, f"{section_name}_citations"):
            object.__setattr__(summary, f"{section_name}_citations", citations)
        elif hasattr(summary, "citations"):
            # Aggregate into flat citations list (election research)
            existing = getattr(summary, "citations", [])
            object.__setattr__(summary, "citations", existing + citations)
        # Re-validate using the summary's own model class
        task.summary = type(summary).model_validate(summary.model_dump())
        task.completed_sections += 1
        if task.status == "pending":
            task.status = "in_progress"
        if task.completed_sections >= task.total_sections:
            task.status = "complete"
```

- [ ] **Step 4: Update `complete()` to use per-task `total_sections`**

Replace `task.completed_sections = TOTAL_SECTIONS` with:

```python
task.completed_sections = task.total_sections
```

- [ ] **Step 5: Verify existing rep research still works**

Run: `cd backend && python -c "
import asyncio
from store.research_store import InMemoryResearchStore
async def test():
    store = InMemoryResearchStore()
    await store.create('test-1')
    task = await store.get('test-1')
    assert task.total_sections == 7
    assert task.status == 'pending'
    print('OK')
asyncio.run(test())
"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add backend/store/research_store.py
git commit -m "feat: parameterize InMemoryResearchStore section count"
```

---

## Task 3: Election Cache Interface + Redis Implementation

**Files:**
- Modify: `backend/store/interfaces.py`
- Modify: `backend/store/redis.py`
- Modify: `backend/store/dependencies.py`

- [ ] **Step 1: Add `ElectionCacheInterface` to `backend/store/interfaces.py`**

```python
from models import ElectionResearchSummary, ResearchSummary

class ElectionCacheInterface(ABC):
    @abstractmethod
    async def get(self, election_name: str, election_date: str, address_hash: str) -> ElectionResearchSummary | None: ...

    @abstractmethod
    async def put(self, election_name: str, election_date: str, address_hash: str, summary: ElectionResearchSummary) -> None: ...

    @abstractmethod
    async def cleanup(self) -> None: ...
```

- [ ] **Step 2: Add `RedisElectionCache` to `backend/store/redis.py`**

```python
from models import ElectionResearchSummary, ResearchSummary

def _election_cache_key(election_name: str, election_date: str, address_hash: str) -> str:
    return f"electioncache:{election_name.lower().strip()}|{election_date}|{address_hash}"


class RedisElectionCache(ElectionCacheInterface):
    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    async def get(self, election_name: str, election_date: str, address_hash: str) -> ElectionResearchSummary | None:
        key = _election_cache_key(election_name, election_date, address_hash)
        try:
            data = await self._r.get(key)
        except Exception as e:
            logger.error(f"Redis GET failed for election {election_name}: {e}")
            return None
        if data is None:
            return None
        return ElectionResearchSummary.model_validate_json(data)

    async def put(self, election_name: str, election_date: str, address_hash: str, summary: ElectionResearchSummary) -> None:
        key = _election_cache_key(election_name, election_date, address_hash)
        try:
            await self._r.set(key, summary.model_dump_json(), ex=REP_CACHE_TTL_SECONDS)
        except Exception as e:
            logger.error(f"Redis SET failed for election {election_name}: {e}")

    async def cleanup(self) -> None:
        pass
```

- [ ] **Step 3: Add `NoOpElectionCache` and `get_election_cache()` to `backend/store/dependencies.py`**

```python
from models import ElectionResearchSummary, ResearchSummary
from store.interfaces import ElectionCacheInterface, RepCacheInterface

_election_cache: ElectionCacheInterface | None = None


class NoOpElectionCache(ElectionCacheInterface):
    async def get(self, election_name: str, election_date: str, address_hash: str) -> ElectionResearchSummary | None:
        return None

    async def put(self, election_name: str, election_date: str, address_hash: str, summary: ElectionResearchSummary) -> None:
        pass

    async def cleanup(self) -> None:
        pass


def get_election_cache() -> ElectionCacheInterface:
    global _election_cache
    if _election_cache is None:
        if os.getenv("REDIS_URL"):
            from store.redis import RedisElectionCache, create_redis_client
            _election_cache = RedisElectionCache(create_redis_client())
            logger.info("Using Redis election cache")
        else:
            _election_cache = NoOpElectionCache()
            logger.info("Election cache disabled (no REDIS_URL)")
    return _election_cache
```

- [ ] **Step 4: Verify imports**

Run: `cd backend && python -c "from store.dependencies import get_election_cache; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/store/interfaces.py backend/store/redis.py backend/store/dependencies.py
git commit -m "feat: add election cache interface with Redis and no-op implementations"
```

---

## Task 4: Google Civic API Service

**Files:**
- Create: `backend/services/elections.py`

- [ ] **Step 1: Create `backend/services/elections.py`**

```python
"""Google Civic Information API client for election data."""

import hashlib
import logging
import os

import httpx

from models import (
    Candidate,
    Contest,
    Election,
    ElectionsResponse,
    PollingLocation,
    VoterInfo,
)

logger = logging.getLogger(__name__)

_CIVIC_API_BASE = "https://www.googleapis.com/civicinfo/v2"

# Map Google Civic API office levels to our level values
_LEVEL_MAP = {
    "country": "federal",
    "administrativeArea1": "state",
    "administrativeArea2": "municipal",
    "locality": "municipal",
    "regional": "municipal",
    "special": "municipal",
    "subLocality1": "municipal",
    "subLocality2": "municipal",
}


def address_hash(address: str) -> str:
    """Deterministic short hash of an address for cache keys."""
    return hashlib.sha256(address.lower().strip().encode()).hexdigest()[:12]


async def fetch_elections(address: str) -> ElectionsResponse:
    """Fetch upcoming elections and ballot info for an address from Google Civic API."""
    api_key = os.environ.get("GOOGLE_CIVIC_API_KEY")
    if not api_key:
        logger.warning("GOOGLE_CIVIC_API_KEY not set, returning empty elections")
        return ElectionsResponse(elections=[])

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{_CIVIC_API_BASE}/voterinfo",
            params={"address": address, "key": api_key},
        )

        if resp.status_code == 400:
            # No elections upcoming for this address
            logger.info(f"No elections found for address (400 response)")
            return ElectionsResponse(elections=[])

        resp.raise_for_status()
        data = resp.json()

    return _parse_civic_response(data)


def _parse_civic_response(data: dict) -> ElectionsResponse:
    """Parse the Google Civic API voterinfo response into our models."""
    election_data = data.get("election", {})
    if not election_data or election_data.get("id") == "0":
        return ElectionsResponse(elections=[])

    # Parse polling location
    polling_location = None
    polling_locations = data.get("pollingLocations", [])
    if polling_locations:
        pl = polling_locations[0]
        addr = pl.get("address", {})
        polling_location = PollingLocation(
            name=addr.get("locationName", "Polling Location"),
            address=_format_civic_address(addr),
            hours=pl.get("pollingHours"),
        )

    # Parse contests and candidates
    contests = []
    for contest_data in data.get("contests", []):
        office = contest_data.get("office", "Unknown Office")
        level = "municipal"  # default
        levels = contest_data.get("level", [])
        if levels:
            level = _LEVEL_MAP.get(levels[0], "municipal")

        district = contest_data.get("district", {})
        district_name = district.get("name")

        candidates = []
        for cand_data in contest_data.get("candidates", []):
            candidates.append(Candidate(
                name=cand_data.get("name", "Unknown"),
                office=office,
                level=level,
                party=cand_data.get("party"),
                photo_url=cand_data.get("photoUrl"),
                contest_name=f"{office} - {district_name}" if district_name else office,
                incumbent=False,  # Civic API doesn't reliably indicate this
            ))

        contests.append(Contest(
            office=office,
            level=level,
            district_name=district_name,
            candidates=candidates,
        ))

    # Parse voter info from state administration body
    voter_info = _parse_voter_info(data)

    # Parse early vote sites and drop-off locations into voter_info
    for site in data.get("earlyVoteSites", []):
        addr = site.get("address", {})
        voter_info.early_vote_sites.append(PollingLocation(
            name=addr.get("locationName", "Early Vote Site"),
            address=_format_civic_address(addr),
            hours=site.get("pollingHours"),
        ))
    for loc in data.get("dropOffLocations", []):
        addr = loc.get("address", {})
        voter_info.drop_off_locations.append(PollingLocation(
            name=addr.get("locationName", "Drop-off Location"),
            address=_format_civic_address(addr),
            hours=loc.get("pollingHours"),
        ))

    # Determine election type from name
    election_name = election_data.get("name", "Unknown Election")
    election_type = _infer_election_type(election_name)

    election = Election(
        name=election_name,
        date=election_data.get("electionDay", ""),
        election_type=election_type,
        polling_location=polling_location,
        voter_info=voter_info,
        contests=contests,
    )

    return ElectionsResponse(elections=[election])


def _parse_voter_info(data: dict) -> VoterInfo:
    """Extract voter info from Civic API state[].electionAdministrationBody."""
    states = data.get("state", [])
    if not states:
        return VoterInfo()

    admin = states[0].get("electionAdministrationBody", {})
    if not admin:
        return VoterInfo()

    return VoterInfo(
        registration_url=admin.get("electionRegistrationUrl"),
        absentee_url=admin.get("absenteeVotingInfoUrl"),
        ballot_info_url=admin.get("ballotInfoUrl"),
        polling_location_url=admin.get("votingLocationFinderUrl"),
        mail_only=data.get("mailOnly", False),
        admin_body_name=admin.get("name"),
        admin_body_url=admin.get("electionInfoUrl"),
    )


def _format_civic_address(addr: dict) -> str:
    """Format a Civic API address object into a single string."""
    parts = [
        addr.get("line1", ""),
        addr.get("line2", ""),
        addr.get("city", ""),
        addr.get("state", ""),
        addr.get("zip", ""),
    ]
    return ", ".join(p for p in parts if p)


def _infer_election_type(name: str) -> str:
    """Guess election type from the election name."""
    lower = name.lower()
    if "runoff" in lower:
        return "runoff"
    if "primary" in lower:
        return "primary"
    if "general" in lower:
        return "general"
    return "general"  # default
```

- [ ] **Step 2: Verify the module imports cleanly**

Run: `cd backend && python -c "from services.elections import fetch_elections, address_hash; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/services/elections.py
git commit -m "feat: add Google Civic API elections service"
```

---

## Task 5: Election Research Pipeline

**Files:**
- Create: `backend/research/election_pipeline.py`
- Create: 2 prompt files in `backend/research/prompts/`

Simplified pipeline: 1 sync LLM call (election context, no web search) + 1 research agent (key issues, web search). Voter info comes from the Civic API, not research.

- [ ] **Step 1: Create election research prompts**

Only one pair needed — for the key issues agent that uses web search.

Create `backend/research/prompts/election_key_issues_system.txt`:
```
You are a nonpartisan political research assistant. Your job is to identify key issues and assess the political significance of an upcoming election.

Today's date is ${current_date}.

## Instructions

1. Perform up to 4 web searches to research this election.
2. Write a concise summary (3-5 sentences) covering:
   - What's politically at stake (balance of power, key competitive races)
   - Top 2-3 issues driving races in this election cycle
   - Local context that shapes how voters in this area think about these issues
3. Embed inline citation markers like [1], [2] after each factual claim.

## Rules

- Every factual claim must cite a search result — do not fabricate sources or URLs
- Be nonpartisan and factual — present all sides
- Keep it concise — short, direct sentences
- Plain text only, no html or markdown allowed
- citations[0] corresponds to [1], citations[1] to [2], etc.
- Max 4 web searches total
```

Create `backend/research/prompts/election_key_issues_user.txt`:
```
Research the political significance and key issues of the $election_name ($election_date) in $state. This is a $election_type election. The user lives near: $address. What's at stake and what issues are driving the races?
```

- [ ] **Step 2: Create `backend/research/election_pipeline.py`**

```python
"""Election research pipeline — sync context generation + async key issues research."""

import asyncio
import logging
import os
from datetime import date
from pathlib import Path
from string import Template

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents import create_agent
from langfuse import observe
from langfuse.langchain import CallbackHandler

from models import Citation, ElectionResearchSummary, SectionResult
from research.pipeline import web_search  # reuse the same search tool
from research.usage import UsageStats, UsageTracker
from store.research_store import InMemoryResearchStore

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

_semaphore = asyncio.Semaphore(2)

ELECTION_TOTAL_SECTIONS = 2  # election_context (sync) + key_issues_and_significance (async)


async def generate_election_context(
    election_name: str,
    election_date: str,
    election_type: str,
    state: str,
) -> str:
    """Generate election type context from LLM training data. No web search needed."""
    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=512,
    )
    prompt = (
        f"In 2-3 sentences, explain what a {election_type} election is and what it means "
        f"for voters. This is the {election_name} on {election_date} in {state}. "
        f"Be concise, nonpartisan, and factual. Plain text only."
    )
    response = await model.ainvoke([HumanMessage(content=prompt)])
    return response.content


@observe(name="election-key-issues-agent")
async def research_key_issues(
    election_name: str,
    election_date: str,
    election_type: str,
    state: str,
    address: str,
) -> tuple[str, list[Citation], UsageStats]:
    """Run one research agent with web search to find key issues and political significance."""
    langfuse_handler = CallbackHandler()
    usage_tracker = UsageTracker()
    model = ChatAnthropic(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=int(os.environ.get("RESEARCH_MAX_TOKENS", "4096")),
    )
    agent = create_agent(
        model,
        tools=[web_search],
        response_format=SectionResult,
    )

    system_template = Template(
        (_PROMPTS_DIR / "election_key_issues_system.txt").read_text()
    )
    user_template = Template(
        (_PROMPTS_DIR / "election_key_issues_user.txt").read_text()
    )

    system_prompt = system_template.substitute(current_date=date.today().isoformat())
    user_prompt = user_template.substitute(
        election_name=election_name,
        election_date=election_date,
        election_type=election_type,
        state=state,
        address=address,
    )

    result = await agent.ainvoke(
        {
            "messages": [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        },
        config={
            "callbacks": [langfuse_handler, usage_tracker],
            "recursion_limit": 15,
            "run_name": f"election:key_issues:{election_name}",
        },
    )

    structured = result["structured_response"]
    logger.info(
        f"Key issues research complete for {election_name}: "
        f"{len(structured.citations)} citations"
    )
    return structured.content, structured.citations, usage_tracker.stats


@observe(name="election-research-pipeline")
async def research_election(
    election_name: str,
    election_date: str,
    election_type: str,
    state: str,
    address: str,
    store: InMemoryResearchStore | None = None,
    research_id: str | None = None,
) -> tuple[ElectionResearchSummary | None, UsageStats]:
    """Generate election context (sync LLM) then research key issues (async web search)."""
    total_usage = UsageStats()
    logger.info(f"Starting election research for {election_name}")

    # Step 1: Generate election context from training data (fast, no web search)
    try:
        context = await generate_election_context(
            election_name, election_date, election_type, state
        )
    except Exception as e:
        logger.error(f"Election context generation failed: {e}", exc_info=True)
        context = ""

    if store and research_id:
        await store.complete_section(research_id, "election_context", context, [])

    # Step 2: Research key issues with web search (slower)
    async with _semaphore:
        try:
            content, citations, usage = await research_key_issues(
                election_name, election_date, election_type, state, address
            )
            total_usage += usage
        except Exception as e:
            logger.error(f"Key issues research failed for {election_name}: {e}", exc_info=True)
            content = ""
            citations = []

        if store and research_id:
            await store.complete_section(
                research_id, "key_issues_and_significance", content, citations
            )

    logger.info(
        f"Election research for {election_name}: "
        f"{total_usage.input_tokens} in / {total_usage.output_tokens} out / "
        f"{total_usage.tool_calls} tool calls"
    )

    if store and research_id:
        task = await store.get(research_id)
        return task.summary if task else None, total_usage

    return None, total_usage
```

- [ ] **Step 3: Verify the module imports**

Run: `cd backend && python -c "from research.election_pipeline import research_election, ELECTION_TOTAL_SECTIONS; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/research/election_pipeline.py backend/research/prompts/election_key_issues_*
git commit -m "feat: add election research pipeline (1 LLM context + 1 web search agent)"
```

---

## Task 6: Elections Router

**Files:**
- Create: `backend/routers/elections.py`
- Modify: `backend/main.py:18-22,97-99`
- Modify: `backend/db.py:59-86`

- [ ] **Step 1: Update `save_research_task()` in `backend/db.py` to accept `task_type`**

Add `task_type: str = "rep"` parameter and include it in the INSERT:

```python
async def save_research_task(
    *,
    research_id: str,
    representative: str,
    input_tokens: int,
    output_tokens: int,
    tool_calls: int,
    status: str,
    model: str | None = None,
    input_cost_per_m: Decimal | None = None,
    output_cost_per_m: Decimal | None = None,
    search_tool: str | None = None,
    cost_per_search: Decimal | None = None,
    environment: str | None = None,
    task_type: str = "rep",
) -> None:
    """Insert a row into the research_tasks table."""
    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO research_tasks (id, representative, input_tokens, output_tokens,
                          tool_calls, status, model, input_cost_per_m,
                          output_cost_per_m, search_tool, cost_per_search, environment, task_type)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        """,
        research_id, representative, input_tokens, output_tokens,
        tool_calls, status, model, input_cost_per_m,
        output_cost_per_m, search_tool, cost_per_search, environment, task_type,
    )
```

- [ ] **Step 2: Create `backend/routers/elections.py`**

```python
import asyncio
import logging
import os
import uuid
from decimal import Decimal

from fastapi import APIRouter, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from db import save_research_task, save_transactions
from models import (
    AddressRequest,
    ElectionResearchRequest,
    ElectionResearchResponse,
    ElectionResearchSummary,
    ElectionsResponse,
)
from research.election_pipeline import ELECTION_TOTAL_SECTIONS, research_election
from services.elections import address_hash, fetch_elections
from store.dependencies import get_election_cache, get_research_store

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

MAX_AUTO_RESEARCH = 3


def _cost_config() -> dict:
    input_cost_env = os.environ.get("ANTHROPIC_INPUT_COST_PER_M")
    output_cost_env = os.environ.get("ANTHROPIC_OUTPUT_COST_PER_M")
    search_cost_env = os.environ.get("COST_PER_SEARCH")
    return {
        "model": os.environ.get("CLAUDE_MODEL"),
        "input_cost_per_m": Decimal(input_cost_env) if input_cost_env else None,
        "output_cost_per_m": Decimal(output_cost_env) if output_cost_env else None,
        "search_tool": os.environ.get("SEARCH_TOOL", "tavily"),
        "cost_per_search": Decimal(search_cost_env) if search_cost_env else None,
        "environment": os.environ.get("ENVIRONMENT", "dev"),
    }


async def _run_election_research(
    research_id: str, req: ElectionResearchRequest
) -> None:
    """Background task: research one election, write to store + cache + DB."""
    store = get_research_store()
    election_cache = get_election_cache()
    addr_hash = address_hash(req.address)

    try:
        summary, usage = await research_election(
            election_name=req.election_name,
            election_date=req.election_date,
            election_type=req.election_type,
            state=req.state,
            address=req.address,
            store=store,
            research_id=research_id,
        )
        if summary is not None:
            await election_cache.put(req.election_name, req.election_date, addr_hash, summary)
        else:
            await store.fail(research_id)
    except Exception as e:
        logger.error(f"Election research {research_id} failed: {e}", exc_info=True)
        await store.fail(research_id)
        return

    cfg = _cost_config()
    try:
        await save_research_task(
            research_id=research_id,
            representative=f"Election: {req.election_name}",
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            tool_calls=usage.tool_calls,
            status="done" if summary else "failed",
            task_type="election",
            **cfg,
        )
        await save_transactions(
            research_task_id=research_id,
            model=cfg["model"],
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            input_cost_per_m=cfg["input_cost_per_m"],
            output_cost_per_m=cfg["output_cost_per_m"],
            search_tool=cfg["search_tool"],
            tool_calls=usage.tool_calls,
            cost_per_search=cfg["cost_per_search"],
        )
    except Exception as e:
        logger.error(f"Election research {research_id}: DB save failed: {e}", exc_info=True)


@router.post("/api/elections")
@limiter.limit("10/minute")
async def get_elections(request: Request, body: AddressRequest) -> ElectionsResponse:
    """Fetch upcoming elections for an address and auto-trigger research."""
    elections_resp = await fetch_elections(body.address)

    # Auto-trigger election research for up to MAX_AUTO_RESEARCH elections
    store = get_research_store()
    election_cache = get_election_cache()
    addr_hash = address_hash(body.address)
    research_ids: dict[str, str] = {}

    # Extract state from address (simple heuristic: second-to-last comma-separated part)
    parts = [p.strip() for p in body.address.split(",")]
    state = parts[-2] if len(parts) >= 3 else parts[-1] if parts else ""
    # Strip zip code if state part contains it (e.g., "TX 78701")
    state = state.split()[0] if state else ""

    for election in elections_resp.elections[:MAX_AUTO_RESEARCH]:
        ekey = f"{election.name}|{election.date}"

        # Skip if already cached
        cached = await election_cache.get(election.name, election.date, addr_hash)
        if cached is not None:
            research_ids[ekey] = "cached"
            continue

        research_id = uuid.uuid4().hex[:12]
        research_ids[ekey] = research_id
        await store.create(
            research_id,
            total_sections=ELECTION_TOTAL_SECTIONS,
            summary=ElectionResearchSummary(),
        )
        req = ElectionResearchRequest(
            election_name=election.name,
            election_date=election.date,
            election_type=election.election_type,
            state=state,
            address=body.address,
        )
        asyncio.create_task(_run_election_research(research_id, req))

    elections_resp.research_ids = research_ids
    return elections_resp


@router.post("/api/election-research")
@limiter.limit("10/minute")
async def start_election_research(
    request: Request, body: ElectionResearchRequest
) -> ElectionResearchResponse:
    """Manually trigger election research (for elections beyond auto-research cap)."""
    election_cache = get_election_cache()
    addr_hash = address_hash(body.address)

    # Check cache
    skip_cache = os.getenv("DISABLE_REP_CACHE", "").lower() in ("true", "1")
    if not skip_cache:
        cached = await election_cache.get(body.election_name, body.election_date, addr_hash)
        if cached is not None:
            return ElectionResearchResponse(
                research_id="cached",
                status="complete",
                summary=cached,
            )

    research_id = uuid.uuid4().hex[:12]
    store = get_research_store()
    await store.create(
        research_id,
        total_sections=ELECTION_TOTAL_SECTIONS,
        summary=ElectionResearchSummary(),
    )
    asyncio.create_task(_run_election_research(research_id, body))

    return ElectionResearchResponse(research_id=research_id, status="pending")


@router.get("/api/election-research/{research_id}")
async def get_election_research(research_id: str) -> ElectionResearchResponse:
    from fastapi import HTTPException
    task = await get_research_store().get(research_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Election research task not found or expired.")
    return ElectionResearchResponse(
        research_id=task.research_id,
        status=task.status,
        summary=task.summary,
    )
```

- [ ] **Step 3: Register elections router in `backend/main.py`**

Add import and include after existing router registrations:

```python
from routers.elections import router as elections_router
```

And in the router registration block:

```python
app.include_router(elections_router)
```

Also add election cache cleanup in the `periodic_cleanup` function:

```python
from store.dependencies import get_election_cache, get_rep_cache, get_research_store

# In periodic_cleanup:
await get_election_cache().cleanup()
```

- [ ] **Step 4: Verify the server starts**

Run: `cd backend && python -c "from routers.elections import router; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/routers/elections.py backend/db.py backend/main.py
git commit -m "feat: add elections router with auto-triggered research"
```

---

## Task 7: Frontend — React Router + AddressContext

**Files:**
- Modify: `frontend/src/main.tsx`
- Rewrite: `frontend/src/App.tsx`
- Create: `frontend/src/contexts/AddressContext.tsx`
- Create: `frontend/src/components/TabNav.tsx`

- [ ] **Step 1: Install react-router-dom**

Run: `cd frontend && npm install react-router-dom`

- [ ] **Step 2: Create `frontend/src/contexts/AddressContext.tsx`**

```tsx
import { createContext, useContext, useState, useCallback } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

interface AddressContextValue {
  address: string | null;
  setAddress: (address: string) => void;
  clearAddress: () => void;
}

const AddressContext = createContext<AddressContextValue | null>(null);

export function AddressProvider({ children }: { children: ReactNode }) {
  const [address, setAddressState] = useState<string | null>(null);
  const navigate = useNavigate();

  const setAddress = useCallback(
    (addr: string) => {
      setAddressState(addr);
      navigate("/reps");
    },
    [navigate]
  );

  const clearAddress = useCallback(() => {
    setAddressState(null);
    navigate("/");
  }, [navigate]);

  return (
    <AddressContext.Provider value={{ address, setAddress, clearAddress }}>
      {children}
    </AddressContext.Provider>
  );
}

export function useAddress() {
  const ctx = useContext(AddressContext);
  if (!ctx) throw new Error("useAddress must be used within AddressProvider");
  return ctx;
}
```

- [ ] **Step 3: Create `frontend/src/components/TabNav.tsx`**

```tsx
import { NavLink } from "react-router-dom";

export function TabNav() {
  return (
    <div className="flex gap-1 border-b mb-6 max-w-4xl mx-auto">
      <NavLink
        to="/reps"
        className={({ isActive }) =>
          `px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            isActive
              ? "border-primary text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`
        }
      >
        My Representatives
      </NavLink>
      <NavLink
        to="/elections"
        className={({ isActive }) =>
          `px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            isActive
              ? "border-primary text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`
        }
      >
        Upcoming Elections
      </NavLink>
    </div>
  );
}
```

- [ ] **Step 4: Create stub `frontend/src/pages/ElectionsPage.tsx`** (full implementation in Task 10)

```tsx
export function ElectionsPage() {
  return <div>Elections page — coming soon</div>;
}
```

- [ ] **Step 5: Rewrite `frontend/src/App.tsx` with router**

```tsx
import { Routes, Route, Navigate } from "react-router-dom";
import { useAddress } from "@/contexts/AddressContext";
import { SearchPage } from "@/pages/SearchPage";
import { RepresentativesPage } from "@/pages/RepresentativesPage";
import { ElectionsPage } from "@/pages/ElectionsPage";
import { TabNav } from "@/components/TabNav";

function RequireAddress({ children }: { children: React.ReactNode }) {
  const { address } = useAddress();
  if (!address) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function ResultsLayout({ children }: { children: React.ReactNode }) {
  const { address, clearAddress } = useAddress();

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-6 py-12">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold tracking-tight mb-2">MyReps</h1>
          <p className="text-muted-foreground">
            Find your elected representatives at every level of government.
          </p>
        </div>

        <div className="flex justify-center mb-6">
          <div className="flex items-center gap-3 text-sm">
            <span className="text-muted-foreground">
              Results for: <strong className="text-foreground">{address}</strong>
            </span>
            <button
              onClick={clearAddress}
              className="text-primary underline underline-offset-2 hover:text-primary/80"
            >
              New search
            </button>
          </div>
        </div>

        <TabNav />
        {children}
      </div>
    </div>
  );
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<SearchPage />} />
      <Route
        path="/reps"
        element={
          <RequireAddress>
            <ResultsLayout>
              <RepresentativesPage />
            </ResultsLayout>
          </RequireAddress>
        }
      />
      <Route
        path="/elections"
        element={
          <RequireAddress>
            <ResultsLayout>
              <ElectionsPage />
            </ResultsLayout>
          </RequireAddress>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
```

- [ ] **Step 6: Update `frontend/src/main.tsx` to include BrowserRouter + AddressProvider**

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AddressProvider } from "@/contexts/AddressContext";
import "./index.css";
import App from "./App.tsx";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <AddressProvider>
        <App />
      </AddressProvider>
    </BrowserRouter>
  </StrictMode>
);
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/main.tsx frontend/src/App.tsx frontend/src/contexts/AddressContext.tsx frontend/src/components/TabNav.tsx frontend/src/pages/ElectionsPage.tsx
git commit -m "feat: add React Router with AddressContext and tab navigation"
```

---

## Task 8: Frontend — SearchPage + RepresentativesPage

**Files:**
- Create: `frontend/src/pages/SearchPage.tsx`
- Create: `frontend/src/pages/RepresentativesPage.tsx`

- [ ] **Step 1: Create `frontend/src/pages/SearchPage.tsx`**

Extract the welcome message and search form from old App.tsx:

```tsx
import { AddressSearch } from "@/components/AddressSearch";
import { useAddress } from "@/contexts/AddressContext";

export function SearchPage() {
  const { setAddress } = useAddress();

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-6 py-12">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold tracking-tight mb-2">MyReps</h1>
          <p className="text-muted-foreground">
            Find your elected representatives at every level of government.
          </p>
        </div>

        <div className="max-w-2xl mx-auto mb-8 text-center space-y-4">
          <p className="text-lg text-muted-foreground">
            You deserve to know who represents you — and what they're doing.
          </p>
          <p className="text-sm text-muted-foreground">
            Most of us only think about our elected officials at election time, and even then we focus on the big races. But the representatives who affect your daily life the most — your state legislators, your city council members — are often the ones you hear about the least.
          </p>
          <p className="text-sm text-muted-foreground">
            MyReps changes that. Enter your address and get every elected official who represents you, from the President to your city council, with up-to-date summaries of what they've been working on and direct contact info so you can reach them.
          </p>
          <p className="text-sm font-semibold text-foreground">
            Know who represents you. Hold them accountable. Make your voice heard.
          </p>
        </div>

        <div className="flex justify-center mb-8">
          <AddressSearch onSearch={setAddress} loading={false} />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/pages/RepresentativesPage.tsx`**

Extract the existing results view from old App.tsx.

**Note:** You must also modify `frontend/src/hooks/useRepresentatives.ts` to expose `fetchedAddress`. Add a ref that tracks the last fetched address and return it:

```typescript
// Add inside useRepresentatives():
const fetchedAddressRef = useRef<string | null>(null);
// Set inside lookup() after successful fetch:
fetchedAddressRef.current = address;
// Add to return:
return { representatives, loading, error, lookup, fetchedAddress: fetchedAddressRef.current };
```

```tsx
import { useEffect } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { RepCard } from "@/components/RepCard";
import { SkeletonCard } from "@/components/SkeletonCard";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useRepresentatives } from "@/hooks/useRepresentatives";
import { useResearch } from "@/hooks/useResearch";
import { useAddress } from "@/contexts/AddressContext";
import type { Representative } from "@/types";

function groupByLevel(reps: Representative[]) {
  const groups: { label: string; level: string; reps: Representative[] }[] = [
    { label: "Federal", level: "federal", reps: [] },
    { label: "State", level: "state", reps: [] },
    { label: "Municipal", level: "municipal", reps: [] },
  ];
  for (const rep of reps) {
    const group = groups.find((g) => g.level === rep.level);
    if (group) group.reps.push(rep);
    else groups[2].reps.push(rep);
  }
  return groups.filter((g) => g.reps.length > 0);
}

export function RepresentativesPage() {
  const { address } = useAddress();
  const { representatives, loading, error, lookup, fetchedAddress } = useRepresentatives();
  const { requestResearch, getStatus, getSummary } = useResearch();

  useEffect(() => {
    // Only fetch if address changed (prevents re-fetch on tab switch)
    if (address && address !== fetchedAddress) lookup(address);
  }, [address, lookup, fetchedAddress]);

  const hasResults = representatives.length > 0;
  const groups = groupByLevel(representatives);

  return (
    <>
      {loading && !hasResults && (
        <div className="space-y-4">
          <p className="text-center text-sm text-muted-foreground">
            Looking up your representatives…
          </p>
          <div className="grid gap-4 grid-cols-1 max-w-4xl mx-auto">
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="text-center p-6 rounded-lg bg-destructive/10 text-destructive">
          {error}
        </div>
      )}

      {hasResults && (
        <div className="space-y-8">
          {groups.map((group) => (
            <Collapsible key={group.level} defaultOpen asChild>
              <section className="max-w-4xl mx-auto">
                <CollapsibleTrigger className="flex w-full items-center gap-2 border-b pb-2 cursor-pointer group">
                  <span className="text-muted-foreground transition-transform group-data-[state=closed]:rotate-0 group-data-[state=open]:rotate-0">
                    <ChevronRight className="h-5 w-5 group-data-[state=open]:hidden" />
                    <ChevronDown className="h-5 w-5 group-data-[state=closed]:hidden" />
                  </span>
                  <h2 className="text-xl font-semibold">
                    {group.label}
                  </h2>
                  <span className="text-sm text-muted-foreground">
                    ({group.reps.length})
                  </span>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <div className="grid gap-4 grid-cols-1 mt-4">
                    {group.reps.map((rep) => (
                      <RepCard
                        key={`${rep.name}-${rep.office}`}
                        rep={rep}
                        researchStatus={getStatus(rep)}
                        summary={getSummary(rep)}
                        onResearch={() => requestResearch(rep)}
                      />
                    ))}
                  </div>
                </CollapsibleContent>
              </section>
            </Collapsible>
          ))}
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 3: Verify frontend builds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors (or only pre-existing ones from ElectionsPage not existing yet — that's Task 10)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/SearchPage.tsx frontend/src/pages/RepresentativesPage.tsx
git commit -m "feat: extract SearchPage and RepresentativesPage from App.tsx"
```

---

## Task 9: Frontend — Election Types + Hooks

**Files:**
- Modify: `frontend/src/types/index.ts`
- Create: `frontend/src/hooks/useElections.ts`
- Create: `frontend/src/hooks/useElectionResearch.ts`

- [ ] **Step 1: Add election types to `frontend/src/types/index.ts`**

Append to the file:

```typescript
export interface PollingLocation {
  name: string;
  address: string;
  hours: string | null;
}

export interface Candidate {
  name: string;
  office: string;
  level: "federal" | "state" | "municipal";
  party: string | null;
  photo_url: string | null;
  contest_name: string;
  incumbent: boolean;
}

export interface Contest {
  office: string;
  level: "federal" | "state" | "municipal";
  district_name: string | null;
  candidates: Candidate[];
}

export interface Election {
  name: string;
  date: string;
  election_type: string;
  polling_location: PollingLocation | null;
  voter_info: VoterInfo | null;
  contests: Contest[];
}

export interface ElectionsResponse {
  elections: Election[];
  research_ids: Record<string, string>;  // "election_name|date" → research_id
}

export interface VoterInfo {
  registration_url: string | null;
  absentee_url: string | null;
  ballot_info_url: string | null;
  polling_location_url: string | null;
  early_vote_sites: PollingLocation[];
  drop_off_locations: PollingLocation[];
  mail_only: boolean;
  admin_body_name: string | null;
  admin_body_url: string | null;
}

export interface ElectionResearchSummary {
  election_context: string | null;
  key_issues_and_significance: string | null;
  citations: Citation[];
}

export interface ElectionResearchResponse {
  research_id: string;
  status: "pending" | "in_progress" | "complete" | "failed";
  summary: ElectionResearchSummary | null;
}
```

- [ ] **Step 2: Create `frontend/src/hooks/useElections.ts`**

```typescript
import { useState, useCallback, useRef, useEffect } from "react";
import type { Election, ElectionsResponse } from "@/types";

const API_URL = import.meta.env.VITE_API_URL;

export function useElections() {
  const [elections, setElections] = useState<Election[]>([]);
  const [researchIds, setResearchIds] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fetchedAddress = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const fetchElections = useCallback(async (address: string) => {
    // Deduplicate: don't re-fetch for same address
    if (fetchedAddress.current === address && elections.length > 0) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    try {
      const resp = await fetch(`${API_URL}/api/elections`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address }),
        signal: controller.signal,
      });

      if (!resp.ok) {
        const data = await resp.json().catch(() => null);
        throw new Error(data?.detail || `Request failed (${resp.status})`);
      }

      const data: ElectionsResponse = await resp.json();
      setElections(data.elections);
      setResearchIds(data.research_ids);
      fetchedAddress.current = address;
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }, [elections.length]);

  return { elections, researchIds, loading, error, fetchElections };
}
```

- [ ] **Step 3: Create `frontend/src/hooks/useElectionResearch.ts`**

```typescript
import { useState, useCallback, useRef } from "react";
import type { ElectionResearchSummary, ElectionResearchResponse } from "@/types";

const API_URL = import.meta.env.VITE_API_URL;
const POLL_INTERVAL_MS = 2000;

export type ElectionResearchStatus = "idle" | "loading" | "complete" | "failed";

function electionKey(name: string, date: string): string {
  return `${name}|${date}`;
}

interface ElectionResearchEntry {
  status: ElectionResearchStatus;
  researchId: string | null;
  summary: ElectionResearchSummary | null;
}

function updateEntry(
  key: string,
  entry: ElectionResearchEntry,
): (prev: Map<string, ElectionResearchEntry>) => Map<string, ElectionResearchEntry> {
  return (prev) => {
    const next = new Map(prev);
    next.set(key, entry);
    return next;
  };
}

export function useElectionResearch() {
  const [entries, setEntries] = useState<Map<string, ElectionResearchEntry>>(new Map());
  const entriesRef = useRef(entries);
  entriesRef.current = entries;
  const pollTimers = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());

  const stopPolling = useCallback((key: string) => {
    const timer = pollTimers.current.get(key);
    if (timer) {
      clearInterval(timer);
      pollTimers.current.delete(key);
    }
  }, []);

  const startPolling = useCallback(
    (key: string, researchId: string) => {
      const timer = setInterval(async () => {
        try {
          const resp = await fetch(`${API_URL}/api/election-research/${researchId}`);
          if (!resp.ok) {
            stopPolling(key);
            setEntries(updateEntry(key, { status: "failed", researchId, summary: null }));
            return;
          }

          const data: ElectionResearchResponse = await resp.json();
          if (data.status === "complete") {
            stopPolling(key);
            setEntries(updateEntry(key, { status: "complete", researchId, summary: data.summary }));
          } else if (data.status === "in_progress" || data.status === "pending") {
            if (data.summary) {
              setEntries(updateEntry(key, { status: "loading", researchId, summary: data.summary }));
            }
          } else if (data.status === "failed") {
            stopPolling(key);
            setEntries(updateEntry(key, { status: "failed", researchId, summary: null }));
          }
        } catch {
          // Network error — keep polling
        }
      }, POLL_INTERVAL_MS);

      pollTimers.current.set(key, timer);
    },
    [stopPolling]
  );

  const trackElectionResearch = useCallback(
    (electionName: string, electionDate: string, researchId: string) => {
      const key = electionKey(electionName, electionDate);
      const existing = entriesRef.current.get(key);
      if (existing && (existing.status === "complete" || existing.status === "loading")) return;

      setEntries(updateEntry(key, { status: "loading", researchId, summary: null }));
      startPolling(key, researchId);
    },
    [startPolling]
  );

  const getElectionStatus = useCallback(
    (electionName: string, electionDate: string): ElectionResearchStatus => {
      return entries.get(electionKey(electionName, electionDate))?.status ?? "idle";
    },
    [entries]
  );

  const getElectionSummary = useCallback(
    (electionName: string, electionDate: string): ElectionResearchSummary | null => {
      return entries.get(electionKey(electionName, electionDate))?.summary ?? null;
    },
    [entries]
  );

  return { trackElectionResearch, getElectionStatus, getElectionSummary };
}
```

- [ ] **Step 4: Verify types compile**

Run: `cd frontend && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/hooks/useElections.ts frontend/src/hooks/useElectionResearch.ts
git commit -m "feat: add election TypeScript types and hooks"
```

---

## Task 10: Frontend — ElectionsPage + ElectionCard + CandidateCard

**Files:**
- Create: `frontend/src/components/CandidateCard.tsx`
- Create: `frontend/src/components/ElectionCard.tsx`
- Create: `frontend/src/pages/ElectionsPage.tsx`

- [ ] **Step 1: Create `frontend/src/components/CandidateCard.tsx`**

Compact version of RepCard for candidates:

```tsx
import type { Candidate, ResearchSummary } from "@/types";
import type { ResearchStatus } from "@/hooks/useResearch";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ChevronDown, ChevronRight } from "lucide-react";
// Reuse ResearchContent from RepCard — we'll need to export it
import { ResearchContent } from "@/components/RepCard";

interface CandidateCardProps {
  candidate: Candidate;
  researchStatus: ResearchStatus;
  summary: ResearchSummary | null;
  onResearch: () => void;
}

export function CandidateCard({
  candidate,
  researchStatus,
  summary,
  onResearch,
}: CandidateCardProps) {
  return (
    <Card className="overflow-hidden">
      <CardContent className="p-4">
        <div className="flex items-center gap-3 mb-3">
          {candidate.photo_url ? (
            <img
              src={candidate.photo_url}
              alt={candidate.name}
              className="w-10 h-10 rounded-full object-cover border border-muted flex-shrink-0"
            />
          ) : (
            <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center text-muted-foreground text-sm font-semibold flex-shrink-0">
              {candidate.name.charAt(0)}
            </div>
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium text-sm">{candidate.name}</span>
              {candidate.incumbent && (
                <Badge variant="outline" className="text-xs">Incumbent</Badge>
              )}
            </div>
            <span className="text-xs text-muted-foreground">
              {candidate.party || "No party"}
            </span>
          </div>
        </div>

        {researchStatus === "idle" && (
          <Button onClick={onResearch} variant="outline" size="sm" className="w-full">
            Generate AI Research
          </Button>
        )}

        {researchStatus === "loading" && !summary && (
          <div className="space-y-1.5">
            <p className="text-xs text-muted-foreground italic">Researching...</p>
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-3/4" />
          </div>
        )}

        {researchStatus === "loading" && summary && (
          <Collapsible defaultOpen>
            <CollapsibleTrigger className="flex w-full items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground cursor-pointer group">
              <ChevronRight className="h-3 w-3 group-data-[state=open]:hidden" />
              <ChevronDown className="h-3 w-3 group-data-[state=closed]:hidden" />
              AI Research (loading...)
            </CollapsibleTrigger>
            <CollapsibleContent>
              <ResearchContent summary={summary} />
            </CollapsibleContent>
          </Collapsible>
        )}

        {researchStatus === "complete" && summary && (
          <Collapsible>
            <CollapsibleTrigger className="flex w-full items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground cursor-pointer group">
              <ChevronRight className="h-3 w-3 group-data-[state=open]:hidden" />
              <ChevronDown className="h-3 w-3 group-data-[state=closed]:hidden" />
              AI Research
            </CollapsibleTrigger>
            <CollapsibleContent>
              <ResearchContent summary={summary} />
            </CollapsibleContent>
          </Collapsible>
        )}

        {researchStatus === "failed" && (
          <Button onClick={onResearch} variant="outline" size="sm" className="w-full">
            Retry Research
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
```

**Note:** This requires exporting `ResearchContent` and `renderInline` from `RepCard.tsx`.

- [ ] **Step 2: Export `ResearchContent` and `renderInline` from RepCard**

In `frontend/src/components/RepCard.tsx`:

Change line 20 from:
```tsx
function renderInline(
```
to:
```tsx
export function renderInline(
```

Change line 113 from:
```tsx
function ResearchContent({ summary }: { summary: ResearchSummary }) {
```
to:
```tsx
export function ResearchContent({ summary }: { summary: ResearchSummary }) {
```

- [ ] **Step 3: Create `frontend/src/components/ElectionCard.tsx`**

```tsx
import type {
  Election,
  ElectionResearchSummary,
  Candidate,
  Citation,
} from "@/types";
import type { ElectionResearchStatus } from "@/hooks/useElectionResearch";
import type { ResearchStatus } from "@/hooks/useResearch";
import type { ResearchSummary } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ChevronDown, ChevronRight } from "lucide-react";
import { CandidateCard } from "@/components/CandidateCard";
import { renderInline } from "@/components/RepCard";

function daysUntil(dateStr: string): number {
  const target = new Date(dateStr + "T00:00:00");
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  return Math.ceil((target.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
}

function renderElectionSection(
  title: string,
  content: string | null,
  citations: Citation[]
) {
  if (content === null) {
    return (
      <div>
        <h4 className="text-xs font-medium text-muted-foreground mb-1">{title}</h4>
        <div className="space-y-1">
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-5/6" />
        </div>
      </div>
    );
  }
  return (
    <div>
      <h4 className="text-xs font-medium text-muted-foreground mb-1">{title}</h4>
      <p className="text-sm leading-relaxed">{renderInline(content, citations)}</p>
    </div>
  );
}

const typeColors: Record<string, string> = {
  primary: "bg-purple-600 text-white",
  general: "bg-blue-600 text-white",
  runoff: "bg-amber-600 text-white",
};

interface ElectionCardProps {
  election: Election;
  researchStatus: ElectionResearchStatus;
  researchSummary: ElectionResearchSummary | null;
  getCandidateResearchStatus: (candidate: Candidate) => ResearchStatus;
  getCandidateResearchSummary: (candidate: Candidate) => ResearchSummary | null;
  onCandidateResearch: (candidate: Candidate) => void;
}

export function ElectionCard({
  election,
  researchStatus,
  researchSummary,
  getCandidateResearchStatus,
  getCandidateResearchSummary,
  onCandidateResearch,
}: ElectionCardProps) {
  const days = daysUntil(election.date);
  const daysLabel = days === 0 ? "Today" : days === 1 ? "Tomorrow" : `${days} days away`;

  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <div className="flex justify-between items-start">
          <div>
            <Badge className={typeColors[election.election_type] || typeColors.general}>
              {election.election_type}
            </Badge>
            <CardTitle className="text-xl mt-2">{election.name}</CardTitle>
          </div>
          <div className="text-right">
            <div className="font-medium">{election.date}</div>
            <div className="text-sm text-muted-foreground">{daysLabel}</div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* AI Election Context */}
        {(researchStatus === "loading" || researchStatus === "complete") && (
          <Collapsible defaultOpen>
            <CollapsibleTrigger className="flex w-full items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground cursor-pointer group">
              <ChevronRight className="h-4 w-4 group-data-[state=open]:hidden" />
              <ChevronDown className="h-4 w-4 group-data-[state=closed]:hidden" />
              AI Election Context
              {researchStatus === "loading" && (
                <span className="ml-1 text-xs italic">(loading...)</span>
              )}
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="space-y-3 mt-2 p-4 rounded-lg bg-muted/30 border">
                {renderElectionSection(
                  "About This Election",
                  researchSummary?.election_context ?? null,
                  []  /* no citations — generated from training data */
                )}
                {renderElectionSection(
                  "Key Issues & Significance",
                  researchSummary?.key_issues_and_significance ?? null,
                  researchSummary?.citations ?? []
                )}
              </div>
            </CollapsibleContent>
          </Collapsible>
        )}

        {/* Polling Location */}
        {election.polling_location && (
          <div className="p-3 rounded-lg bg-muted/30 border">
            <h4 className="text-xs font-medium text-muted-foreground mb-1">Polling Location</h4>
            <div className="text-sm font-medium">{election.polling_location.name}</div>
            <div className="text-sm text-muted-foreground">{election.polling_location.address}</div>
            {election.polling_location.hours && (
              <div className="text-sm text-muted-foreground">Hours: {election.polling_location.hours}</div>
            )}
          </div>
        )}

        {/* Voter Info (from Civic API, not research) */}
        {election.voter_info && (
          <div className="p-3 rounded-lg bg-muted/30 border space-y-2">
            <h4 className="text-xs font-medium text-muted-foreground">Voter Resources</h4>
            <div className="flex flex-wrap gap-3 text-sm">
              {election.voter_info.registration_url && (
                <a href={election.voter_info.registration_url} target="_blank" rel="noopener noreferrer" className="text-primary underline underline-offset-2 hover:text-primary/80">Register to Vote</a>
              )}
              {election.voter_info.absentee_url && (
                <a href={election.voter_info.absentee_url} target="_blank" rel="noopener noreferrer" className="text-primary underline underline-offset-2 hover:text-primary/80">Absentee/Mail-In Voting</a>
              )}
              {election.voter_info.ballot_info_url && (
                <a href={election.voter_info.ballot_info_url} target="_blank" rel="noopener noreferrer" className="text-primary underline underline-offset-2 hover:text-primary/80">Ballot Information</a>
              )}
            </div>
            {election.voter_info.mail_only && (
              <p className="text-xs text-muted-foreground">This is a mail-only election.</p>
            )}
            {election.voter_info.early_vote_sites.length > 0 && (
              <div>
                <h5 className="text-xs text-muted-foreground font-medium mt-2">Early Vote Sites</h5>
                {election.voter_info.early_vote_sites.map((site, i) => (
                  <div key={i} className="text-sm">{site.name} — {site.address}{site.hours ? ` (${site.hours})` : ""}</div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* What's on your ballot */}
        {election.contests.length > 0 && (
          <div>
            <h3 className="font-semibold mb-4">What's on your ballot</h3>
            <div className="space-y-6">
              {election.contests.map((contest) => (
                <div key={contest.office}>
                  <div className="text-xs uppercase tracking-wide text-muted-foreground border-b pb-1 mb-3">
                    {contest.office}
                    {contest.district_name && (
                      <span className="ml-1">— {contest.district_name}</span>
                    )}
                  </div>
                  <div className="grid gap-3 grid-cols-1 sm:grid-cols-2">
                    {contest.candidates.map((candidate) => (
                      <CandidateCard
                        key={`${candidate.name}-${candidate.office}`}
                        candidate={candidate}
                        researchStatus={getCandidateResearchStatus(candidate)}
                        summary={getCandidateResearchSummary(candidate)}
                        onResearch={() => onCandidateResearch(candidate)}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* No contests */}
        {election.contests.length === 0 && (
          <p className="text-sm text-muted-foreground italic">
            Candidate information not yet available for this election.
          </p>
        )}

        {/* Referenda placeholder */}
        <div className="border border-dashed rounded-lg p-4">
          <p className="text-sm text-muted-foreground italic">
            Referenda &amp; propositions — coming soon
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 4: Create `frontend/src/pages/ElectionsPage.tsx`**

```tsx
import { useEffect } from "react";
import { useAddress } from "@/contexts/AddressContext";
import { useElections } from "@/hooks/useElections";
import { useElectionResearch } from "@/hooks/useElectionResearch";
import { useResearch } from "@/hooks/useResearch";
import { ElectionCard } from "@/components/ElectionCard";
import { SkeletonCard } from "@/components/SkeletonCard";
import type { Candidate, Representative } from "@/types";

function candidateToRep(candidate: Candidate): Representative {
  return {
    name: candidate.name,
    office: candidate.office,
    level: candidate.level,
    party: candidate.party,
    photo_url: candidate.photo_url,
    contact: { website: null, phone: null, email: null },
  };
}

export function ElectionsPage() {
  const { address } = useAddress();
  const { elections, researchIds, loading, error, fetchElections } = useElections();
  const { trackElectionResearch, getElectionStatus, getElectionSummary } = useElectionResearch();
  const { requestResearch, getStatus, getSummary } = useResearch();

  useEffect(() => {
    if (address) fetchElections(address);
  }, [address, fetchElections]);

  // Start polling for auto-triggered election research once we have research IDs
  useEffect(() => {
    for (const [key, researchId] of Object.entries(researchIds)) {
      if (researchId === "cached") continue;
      const [name, date] = key.split("|");
      trackElectionResearch(name, date, researchId);
    }
  }, [researchIds, trackElectionResearch]);

  const handleCandidateResearch = (candidate: Candidate) => {
    requestResearch(candidateToRep(candidate));
  };

  return (
    <>
      {loading && (
        <div className="space-y-4">
          <p className="text-center text-sm text-muted-foreground">
            Looking up upcoming elections…
          </p>
          <div className="grid gap-4 grid-cols-1 max-w-4xl mx-auto">
            {Array.from({ length: 2 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="text-center p-6 rounded-lg bg-destructive/10 text-destructive">
          {error}
        </div>
      )}

      {!loading && elections.length === 0 && !error && (
        <div className="text-center p-8">
          <p className="text-muted-foreground">
            No upcoming elections found for your address.
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            Election data becomes available when election authorities publish ballot information.
          </p>
        </div>
      )}

      {elections.length > 0 && (
        <div className="space-y-6 max-w-4xl mx-auto">
          {elections.map((election) => (
            <ElectionCard
              key={`${election.name}-${election.date}`}
              election={election}
              researchStatus={getElectionStatus(election.name, election.date)}
              researchSummary={getElectionSummary(election.name, election.date)}
              getCandidateResearchStatus={(c) => getStatus(candidateToRep(c))}
              getCandidateResearchSummary={(c) => getSummary(candidateToRep(c))}
              onCandidateResearch={handleCandidateResearch}
            />
          ))}
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 5: Verify frontend builds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/CandidateCard.tsx frontend/src/components/ElectionCard.tsx frontend/src/components/RepCard.tsx frontend/src/pages/ElectionsPage.tsx
git commit -m "feat: add ElectionsPage with ElectionCard and CandidateCard components"
```

---

## Task 11: Integration Verification

- [ ] **Step 1: Run the frontend build**

Run: `cd frontend && npm run build`
Expected: Successful build with no errors

- [ ] **Step 2: Verify backend starts cleanly**

Run: `cd backend && python -c "from main import app; print('Routes:', [r.path for r in app.routes]); print('OK')"`
Expected: Should list all routes including `/api/elections`, `/api/election-research`, `/api/election-research/{research_id}`

- [ ] **Step 3: Run the migration** (if database is available)

Run: `cd backend && python -c "
import asyncio
from db import get_pool
async def migrate():
    pool = await get_pool()
    with open('migrations/002_add_task_type_to_research_tasks.sql') as f:
        await pool.execute(f.read())
    print('Migration OK')
asyncio.run(migrate())
"`

- [ ] **Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "feat: complete upcoming elections feature integration"
```

---

## Task 12: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md with elections architecture info**

Add to the Architecture section, after the existing research pipeline description:

- Document the elections endpoint (`POST /api/elections`)
- Document the election research pipeline (3 sections)
- Document the `services/elections.py` service
- Document new frontend routes (`/reps`, `/elections`)
- Document `AddressContext` and `TabNav`
- Update the Environment Variables section if any new vars were added
- Add `react-router-dom` to the frontend dependencies description

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with elections feature architecture"
```
