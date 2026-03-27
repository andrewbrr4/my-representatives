# MyReps

Find your elected representatives at every level of government — federal, state, and municipal — with on-demand AI-researched summaries.

- [Product mission & principles](./docs/MISSION.md)
- [Design approach & challenges](./docs/DESIGN.md)
- [Infrastructure & deployment](./docs/INFRASTRUCTURE.md)

## How It Works

### Representatives
1. Enter your address
2. The backend resolves your address to representatives via two concurrent lookups:
   - **Federal:** Census Geocoder (free) → US Congress API for senators + house rep
   - **State + municipal:** Cicero API for all other elected officials
3. Representatives appear instantly with basic info and contact links
4. Click "Generate AI Research" on any rep to trigger on-demand research — 7 focused Claude agents research different sections (background, policy positions, legislative record, etc.) using Tavily web search
5. Research results stream into the card section-by-section as agents complete, always rendered top-down (a section stays as a skeleton until all preceding sections are done); cached for 3 days

### Elections
1. Switch to the Elections tab after entering your address
2. The backend calls the Google Civic API to find upcoming elections, ballot contests, candidates, and voter info for your address
3. Up to 3 elections are automatically researched by AI (election context + key issues/significance)
4. Election cards show voter info (registration links, absentee info, early voting sites, drop-off locations) and ballot contests with candidates
5. Click on any candidate to trigger the same on-demand AI research used for representatives

## Prerequisites

- Python 3.13+ (via conda)
- Node.js 22+
- `gcloud` CLI (for Cloud SQL Auth Proxy)

## API Keys

Create a `.env` file at the project root:

```env
ANTHROPIC_API_KEY=...          # console.anthropic.com
TAVILY_API_KEY=...             # tavily.com (free tier available)
US_CONGRESS_API_KEY=...        # api.congress.gov (free)
CICERO_API_KEY=...             # cicerodata.com (paid, state + municipal data)
GOOGLE_CIVIC_API_KEY=...       # Google Cloud Console (election/ballot data via Civic Information API)
CLAUDE_MODEL=claude-sonnet-4-6 # model for research agents
RESEARCH_MAX_TOKENS=32768      # max tokens per section agent

# Langfuse tracing (optional)
LANGFUSE_SECRET_KEY=...
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com

# Cloud SQL — local dev (via auth proxy — see below)
DATABASE_URL=postgresql://postgres:<password>@127.0.0.1:5432/postgres
# Cloud SQL — Cloud Run (uses Unix socket from proxy sidecar instead of DATABASE_URL)
# DB_SOCKET_PATH=/cloudsql/my-representatives-489301:us-central1:my-representatives
# DB_NAME=postgres
# DB_USER=postgres
# DB_PASSWORD=<password>

# Cost tracking (recorded per research task for historical analysis)
ANTHROPIC_INPUT_COST_PER_M=3      # USD per million input tokens
ANTHROPIC_OUTPUT_COST_PER_M=15    # USD per million output tokens
COST_PER_SEARCH=0.008             # USD per Tavily search
ENVIRONMENT=dev                   # "dev" or "prod" — recorded in research_tasks table
```

The frontend also needs a `frontend/.env`:

```env
VITE_GOOGLE_PLACES_API_KEY=... # Google Places API (New) — restrict by HTTP referrer
```

### Optional env vars

| Variable | Default | Purpose |
|----------|---------|---------|
| `REP_CACHE_TTL_SECONDS` | `259200` (3 days) | How long cached research stays valid |
| `JOB_TTL_SECONDS` | `1800` (30min) | How long research task state is kept in memory |
| `DISABLE_REP_CACHE` | `false` | Skip research cache globally (useful for testing pipeline changes) |
| `REDIS_URL` | _(none)_ | When set, uses Redis for rep cache; otherwise no caching |
| `SEARCH_TOOL` | `tavily` | Search provider name, recorded in research_tasks table for cost tracking |
| `ENVIRONMENT` | `dev` | Recorded in research_tasks table to distinguish dev vs prod usage |

## Running Locally

### 1. Cloud SQL Auth Proxy

The backend persists usage data to Cloud SQL. Locally, you connect via the auth proxy (uses your `gcloud` IAM credentials — no public IP or IP allowlisting needed):

```bash
cloud-sql-proxy my-representatives-489301:us-central1:my-representatives --port 5432 &
```

This proxies `localhost:5432` to the Cloud SQL instance. Make sure `DATABASE_URL` in `.env` points to `127.0.0.1`.

```bash
# Check if it's running
pgrep -fl cloud-sql-proxy

# Stop it
pkill cloud-sql-proxy
```

If you don't need database persistence, you can skip this — the app still works, it just won't save research usage data.

### 2. Start the app

**Without Docker:**

```bash
conda activate my-reps

# Backend (port 8000)
cd backend
pip install -r requirements.txt  # first time only
uvicorn main:app --reload

# Frontend (port 5173, separate terminal)
cd frontend
npm install  # first time only
npm run dev
```

**With Docker Compose:**

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000

## Tech Stack

- **Frontend:** React + TypeScript + Vite + Tailwind CSS v4 + shadcn/ui + TanStack Query
- **Backend:** FastAPI (Python 3.13+)
- **LLM:** Anthropic Claude with tool use (model configurable via `CLAUDE_MODEL`)
- **Web Search:** Tavily API
- **Representative Data:** US Congress API (federal) + Cicero API (state/municipal)
- **Election Data:** Google Civic Information API (elections, ballot contests, candidates, voter info)
- **Database:** Cloud SQL PostgreSQL (usage tracking)
- **Caching:** Redis via Memorystore (production) / in-memory (local dev)
- **Tracing:** Langfuse
