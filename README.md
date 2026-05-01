# MyReps — [knowmyreps.org](https://knowmyreps.org)

Find your elected representatives at every level of government — federal, state, and municipal — with on-demand AI-researched summaries.

## How It Works

### Representatives
1. Enter your address
2. Two concurrent lookups find your reps: Census Geocoder + US Congress API (federal), Cicero API (state + municipal)
3. Representatives appear instantly with basic info and contact links
4. Click "Generate AI Research" on any rep — the active overview pipeline researches them. **Production currently runs `v4`** (LangGraph breadth + adaptive depth subagent + formatter). The alternative paradigm `v1` (per-section streaming with skeletons) is also supported and selectable via `OVERVIEW_PIPELINE_VERSION`. v2/v3 are earlier iterations kept for comparison; see [docs/rep-overview-versions.md](./docs/rep-overview-versions.md) for the full version history.
5. v1 streams in section-by-section; v4 renders the full bullet block once the formatter completes. Results cached for 3 days.
6. Search for an issue (e.g., "housing affordability") to see how your reps relate to it

### Elections
1. Switch to the Elections tab after entering your address
2. Google Civic API returns upcoming elections, ballot contests, candidates, and voter info
3. Up to 3 elections are auto-researched by AI (ballot overview)
4. Election cards show voter info (registration, absentee, early voting, drop-off locations) and ballot contests
5. Click any candidate for the same on-demand AI research

## Running Locally

Prerequisites: Python 3.13+ (conda), Node.js 22+, API keys in `.env` ([full list in CLAUDE.md](./CLAUDE.md)).

```bash
# Cloud SQL Auth Proxy (optional — app works without it, just won't persist usage data)
cloud-sql-proxy my-representatives-489301:us-central1:my-representatives --port 5432 &

# Backend (port 8000)
conda activate my-reps
cd backend
pip install -r requirements.txt  # first time only
uvicorn main:app --reload

# Frontend (port 5173, separate terminal)
cd frontend
npm install  # first time only
npm run dev

# Or just use Docker
docker compose up --build
```

```bash
# Other useful commands
cd frontend && npx shadcn@latest add <component>  # add shadcn component
cd frontend && npm run build                       # type-check + production build
cd frontend && npm run lint                        # ESLint
cd frontend && npx tsc --noEmit                    # type-check only
pgrep -fl cloud-sql-proxy                          # check if proxy is running
pkill cloud-sql-proxy                              # stop proxy
```

## Tech Stack

- **Frontend:** React + TypeScript + Vite + Tailwind CSS v4 + shadcn/ui + TanStack Query
- **Backend:** FastAPI (Python 3.13+)
- **LLM:** Anthropic Claude with tool use (model configurable via `CLAUDE_MODEL`)
- **Web Search:** Tavily API
- **Representative Data:** US Congress API (federal) + Cicero API (state/municipal)
- **Election Data:** Google Civic Information API
- **Database:** Cloud SQL PostgreSQL (usage tracking)
- **Caching:** Redis via Memorystore (production) / none (local dev)
- **Tracing:** Langfuse

## Docs

| Doc | Purpose |
|-----|---------|
| [CLAUDE.md](./CLAUDE.md) | Dev reference — architecture, commands, env vars, all implementation details |
| [MISSION.md](./docs/MISSION.md) | Product vision and principles |
| [DESIGN.md](./docs/DESIGN.md) | Design approach, card sections, open challenges |
| [rep-overview-versions.md](./docs/rep-overview-versions.md) | History and architecture of the v1/v2/v3/v4 rep overview pipelines |
| [INFRASTRUCTURE.md](./docs/INFRASTRUCTURE.md) | GCP deployment, secrets, networking |
| [V4_PERFORMANCE.md](./docs/initiatives/V4_PERFORMANCE.md) | Active priority initiative — v4 pipeline philosophy + per-node latency/quality tuning |
| [FRONTEND_ELI5.md](./frontend/FRONTEND_ELI5.md) | Frontend explained for backend devs |
| [initiatives/](./docs/initiatives/) | Feature explorations (cost tracking, feedback, election API research) |
