# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

MyReps — a full-stack app where a user enters their address and gets a list of representatives (municipal, state, federal) with AI-researched summaries. No auth, no database, no caching.

**Read [MISSION.md](./MISSION.md) before making any changes.** It defines the product vision, problem statement, and design principles that guide all decisions.

## Commands

### Backend
```bash
conda activate my-reps          # conda env already created
cd backend
uvicorn main:app --reload       # runs on :8000
```

### Frontend
```bash
cd frontend
npm run dev          # Vite dev server on :5173
npm run build        # type-check + production build
npm run lint         # ESLint
npx tsc --noEmit     # type-check only
```

### Docker
```bash
docker compose up --build    # runs both services
```

### Adding shadcn components
```bash
cd frontend && npx shadcn@latest add <component-name>
```

## Architecture

**Backend (FastAPI, Python 3.13+):** Single endpoint `POST /api/representatives`.

Request flow:
1. `routers/representatives.py` receives address → fans out two lookups concurrently:
   - `services/congress.py` for **federal** reps (US Senators + House Rep)
   - `services/civic.py` for **state + municipal** reps
2. `services/congress.py` uses the Census Geocoder (free, no key) to resolve address → state + congressional district, then calls the US Congress API (`/v3/member/congress/{congress}/{state}`) to get senators and the district's House rep with full detail (photo, phone, website, party)
3. `services/civic.py` calls Cicero API (`/v3.1/official`), maps `district_type` to `state`/`municipal` levels, filters out appointed and federal officials, returns list of `Representative` models
4. `routers/representatives.py` fans out `services/research.py` for all reps concurrently via `asyncio.gather`
5. `services/research.py` runs a Claude agent (claude-sonnet-4-20250514) with a Tavily `web_search` tool in an agentic loop (up to 5 iterations) to produce a 2-3 paragraph summary per rep
6. Results are sorted by level priority and returned

All models are in `backend/models.py`. Backend imports use bare module names (not relative) since uvicorn runs from the `backend/` directory.

**Frontend (React + TypeScript + Vite + Tailwind v4 + shadcn/ui):** Single-page app with two states: search and results.

- `src/hooks/useRepresentatives.ts` — manages API call state (loading, error, data)
- `src/components/AddressSearch.tsx` — address input form
- `src/components/RepCard.tsx` — representative card with photo, badge, summary, contacts
- `src/components/SkeletonCard.tsx` — loading placeholder
- `src/components/ui/` — shadcn components (owned copies, not library imports)
- `@/` path alias maps to `src/` (configured in both vite.config.ts and tsconfig.app.json)

Frontend talks to backend via `fetch()` to `http://localhost:8000`. CORS is configured in `backend/main.py`.

## Environment Variables

Required in `.env` at project root:
- `ANTHROPIC_API_KEY`
- `TAVILY_API_KEY`
- `CICERO_API_KEY` — [cicerodata.com](https://www.cicerodata.com/) (paid, state + municipal elected official data)
- `US_CONGRESS_API_KEY` — [api.congress.gov](https://api.congress.gov/) (free, federal legislators)
- `GOOGLE_CIVIC_API_KEY` — kept for future election/ballot data via `voterinfo` endpoint

Backend loads these via `python-dotenv` at startup.
