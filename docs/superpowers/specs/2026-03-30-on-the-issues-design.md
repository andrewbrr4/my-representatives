# On the Issues — Design Spec

**Date:** 2026-03-30
**Status:** Approved for implementation

## Summary

Users can enter a political issue (e.g. "gun control", "AI", "immigration") and see where a specific representative or candidate stands on that issue. Returns a concise, scannable list of bullet points with citations — voting record, public statements, funding connections, concrete actions.

This is backend-first. Frontend placement is undecided and will be designed later with a UI expert. The backend must be flexible enough to support both per-card (single rep + issue) and batch (multiple reps + same issue) patterns.

## Core Concepts

### Research unit: per-rep-per-issue

Each research task answers: "Where does [rep] stand on [issue]?" The user already knows what the issue is — they want the receipts.

Applies to both representatives (from `/reps`) and candidates (from `/elections`).

### Single-section output

One agent, one list result. 3-5 bullet points covering voting record, public statements, funding ties, and concrete actions. Flat citation list. No multi-section incremental delivery — the result arrives as a single unit.

This is intentional: the existing per-rep research already risks information overload with 7 sections. Issue stance should be a quick scan, not another essay.

## Issue Normalization

### Problem

Users will type the same issue many different ways: "AI", "artificial intelligence", "machine learning regulation", "tech regulation". These should all resolve to the same cached research. Additionally, since this is the first feature exposing users to LLM input, we need prompt injection protection.

### Solution: taxonomy + LLM matching

A static taxonomy file (`backend/research/issues_taxonomy.json`) contains known political issues:

```json
[
  {
    "id": "artificial_intelligence",
    "label": "Artificial Intelligence",
    "aliases": ["AI", "machine learning", "tech regulation"]
  },
  {
    "id": "gun_control",
    "label": "Gun Control",
    "aliases": ["guns", "2nd amendment", "second amendment", "firearm regulation", "gun rights"]
  }
]
```

An LLM call (using `CLAUDE_MODEL` per project convention) classifies user input into one of three buckets:

1. **Known issue** — matches a taxonomy entry. Returns canonical `id` and `label`. Cache-friendly.
2. **Novel legitimate issue** — a real political issue not in the taxonomy (e.g. "Iran War" during a new conflict). The LLM generates a canonical `id` and `label`. Accepted but less likely to get cache hits.
3. **Rejected** — not a political issue, or prompt injection attempt. Returns a generic error: "We couldn't match that to a political issue. Try something like 'gun control' or 'immigration'."

The taxonomy serves double duty: it's both a cache optimization layer (known issues get deterministic keys) and a prompt injection safeguard (the LLM's job is classification against known categories, not open-ended generation from user input). The rejection message is always the same static string — no information leakage about the taxonomy or why the input was rejected.

### Endpoint

```
POST /api/issue-match
```

**Request:**
```json
{ "query": "AI" }
```

**Response (known match):**
```json
{ "matched": true, "issue": { "id": "artificial_intelligence", "label": "Artificial Intelligence" }, "novel": false }
```

**Response (novel legitimate issue):**
```json
{ "matched": true, "issue": { "id": "iran_war", "label": "Iran War" }, "novel": true }
```

**Response (rejected):**
```json
{ "matched": false, "message": "We couldn't match that to a political issue. Try something like 'gun control' or 'immigration'." }
```

Separating normalization from research lets the frontend validate early (on blur, on submit) before committing to a research task.

## Issue Stance Research Pipeline

### New file: `backend/research/issue_pipeline.py`

Single research agent using the established pattern:

- **LLM:** `ChatAnthropic` with `CLAUDE_MODEL`
- **Tool:** Tavily `web_search`, max 5 searches
- **Recursion limit:** 15
- **Semaphores:** Same as existing research (`_semaphore` for concurrent tasks, `_search_semaphore` for concurrent searches)
- **Output model:** `ListSectionResult` (items + citations) — reuses existing model

### Prompt files

- `backend/research/prompts/issue_stance_system.txt` — system prompt with role, rules, formatting guidelines
- `backend/research/prompts/issue_stance_user.txt` — user prompt template

**Template variables:** `$name`, `$office`, `$issue_label`, `${current_date}`

**Prompt guidance:**
- Focus on verifiable actions: votes cast, bills sponsored/co-sponsored, public statements on record, PAC/donor connections
- Nonpartisan and factual — no characterization of positions as "good" or "bad"
- Every factual claim must cite a search result
- 3-5 bullet items, each a concise factual statement with inline citation markers
- Same citation format as existing research: `[1]`, `[2]` referencing flat citations list

### Usage tracking

- `UsageTracker` callback handler (same as existing pipelines)
- `task_type="issue"` in `save_research_task()`
- Costs persisted to `research_tasks` and `transactions` tables

## Data Models

### `IssueStanceSummary` (new, in `models.py`)

```python
class IssueStanceSummary(BaseModel):
    stance_summary: list[str] | None = None  # 3-5 bullet points
    citations: list[Citation] = []           # flat citation list

    SECTION_NAMES: ClassVar[list[str]] = ["stance_summary"]
```

Single section. `total_sections=1` when creating `InMemoryResearchStore` task.

Uses flat `citations` list (like `ElectionResearchSummary`, not per-section like `ResearchSummary`). The existing store's `complete_section()` handles this via `hasattr` detection — no store changes needed.

### `IssueMatchRequest` / `IssueMatchResponse` (new, in `models.py`)

```python
class IssueMatchRequest(BaseModel):
    query: str

class IssueInfo(BaseModel):
    id: str
    label: str

class IssueMatchResponse(BaseModel):
    matched: bool
    issue: IssueInfo | None = None
    novel: bool = False
    message: str | None = None  # only set on rejection
```

### `IssueResearchRequest` (new, in `models.py`)

```python
class IssueResearchRequest(BaseModel):
    representative: Representative
    issue_id: str
    issue_label: str
```

### `IssueResearchResponse` (new, in `models.py`)

Follows the same shape as existing research responses:

```python
class IssueResearchResponse(BaseModel):
    research_id: str
    status: str  # "pending" | "in_progress" | "complete" | "failed"
    summary: IssueStanceSummary | None = None
```

## Router & Endpoints

### New file: `backend/routers/issues.py`

Three endpoints:

```
POST /api/issue-match
  - LLM call to classify user input against taxonomy
  - No research triggered
  - Returns IssueMatchResponse

POST /api/issue-research
  - Accepts IssueResearchRequest (representative + issue_id + issue_label)
  - Checks IssueCacheInterface first (key: rep name + office + issue_id)
  - Cache hit → returns immediately with status "complete" + summary
  - Cache miss → creates InMemoryResearchStore task (total_sections=1)
  - Spawns asyncio.create_task for background research
  - Returns IssueResearchResponse with status "pending"
  - Background task: runs agent, caches result, persists costs to DB

GET /api/issue-research/{research_id}
  - Polls task progress
  - Returns IssueResearchResponse with current status + summary
```

Registered in `main.py` alongside existing routers.

## Caching

### New: `IssueCacheInterface` (in `store/interfaces.py`)

```python
class IssueCacheInterface(ABC):
    @abstractmethod
    async def get(self, name: str, office: str, issue_id: str) -> IssueStanceSummary | None: ...

    @abstractmethod
    async def put(self, name: str, office: str, issue_id: str, summary: IssueStanceSummary) -> None: ...
```

### New: `RedisIssueCache` (in `store/redis.py`)

Cache key format: `issue:{name}:{office}:{issue_id}` (normalized/lowered). Same TTL as rep cache (`REP_CACHE_TTL_SECONDS`).

### New: `NoOpIssueCache` (in `store/redis.py`)

Used when `REDIS_URL` is not set. Same pattern as existing `NoOpRepCache`.

### Singleton: `get_issue_cache()` (in `store/dependencies.py`)

Follows the existing lazy singleton pattern.

## Data Flow

```
1. User enters "AI"
     → POST /api/issue-match
     → LLM classifies against taxonomy
     → Returns { matched: true, issue: { id: "artificial_intelligence", label: "Artificial Intelligence" } }

2. User triggers research on Rep X + this issue
     → POST /api/issue-research { representative: RepX, issue_id: "artificial_intelligence", issue_label: "Artificial Intelligence" }
     → Check cache: issue:rep_x:senator:artificial_intelligence
     → Cache miss → create task, spawn agent
     → Agent searches web for "Rep X stance on artificial intelligence"
     → Writes result to InMemoryResearchStore

3. Frontend polls
     → GET /api/issue-research/{research_id}
     → Returns IssueResearchResponse with status + summary (bullet list + citations)
```

## Existing Code Changes

Minimal changes to existing code:

- **`main.py`** — register new router
- **`models.py`** — add new models (IssueStanceSummary, IssueMatchRequest/Response, IssueResearchRequest/Response)
- **`store/interfaces.py`** — add `IssueCacheInterface`
- **`store/redis.py`** — add `RedisIssueCache` and `NoOpIssueCache`
- **`store/dependencies.py`** — add `get_issue_cache()` singleton
- **`db.py`** — no changes needed (`task_type` column already accepts arbitrary strings)

No changes to existing research pipelines, store logic, or existing routers.

## New Files

| File | Purpose |
|------|---------|
| `backend/routers/issues.py` | Router with 3 endpoints |
| `backend/research/issue_pipeline.py` | Single-agent research pipeline |
| `backend/research/issues_taxonomy.json` | Static issue taxonomy |
| `backend/research/prompts/issue_stance_system.txt` | System prompt for stance agent |
| `backend/research/prompts/issue_stance_user.txt` | User prompt template |

## Future Vision

These ideas are documented for context but are **not in scope** for initial implementation.

### Dynamic taxonomy updates
A background job polls news APIs (or aggregates trending search terms) for emerging political issues and proposes additions to the taxonomy. Example: "Iran War" wouldn't have existed as an issue a month ago, but user demand or news trends would surface it automatically.

### User-driven taxonomy growth
Novel legitimate issues that get researched N+ times are flagged for review and potentially promoted to canonical taxonomy entries. This creates a feedback loop where the taxonomy evolves based on actual user interest.

### Batch/comparison mode
`POST /api/issue-research-batch` accepts multiple representatives + one issue, returns multiple `research_id`s. Primary use case: election candidate comparisons ("where do all candidates in this race stand on healthcare?"). The per-rep-per-issue research unit is already the right granularity — batch mode just orchestrates multiple concurrent requests.

### Frontend placement options (for UI expert)
- **Per-card button** on `/reps` page — user enters issue per rep
- **Global issue input** on `/elections` page — enters issue once, triggers batch research across candidates in a race
- **Dedicated `/issues` page** — standalone issue exploration experience
