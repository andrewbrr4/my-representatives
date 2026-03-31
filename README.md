# MyReps — [knowmyreps.org](https://knowmyreps.org)

Find your elected representatives at every level of government — federal, state, and municipal — with on-demand AI-researched summaries.

## How It Works

### Representatives
1. Enter your address
2. Two concurrent lookups find your reps: Census Geocoder + US Congress API (federal), Cicero API (state + municipal)
3. Representatives appear instantly with basic info and contact links
4. Click "Generate AI Research" on any rep — 7 focused Claude agents research different sections (background, policy positions, legislative record, etc.) using Tavily web search
5. Research streams in section-by-section as agents complete; cached for 3 days

### Elections
1. Switch to the Elections tab after entering your address
2. Google Civic API returns upcoming elections, ballot contests, candidates, and voter info
3. Up to 3 elections are auto-researched by AI (election context + key issues)
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
| [INFRASTRUCTURE.md](./docs/INFRASTRUCTURE.md) | GCP deployment, secrets, networking |
| [PERFORMANCE.md](./docs/PERFORMANCE.md) | Performance audit and optimization roadmap |
| [FRONTEND_ELI5.md](./frontend/FRONTEND_ELI5.md) | Frontend explained for backend devs |
| [initiatives/](./docs/initiatives/) | Feature explorations (cost tracking, feedback, election API research) |
