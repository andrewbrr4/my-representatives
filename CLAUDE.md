# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

MyReps — a full-stack app where a user enters their address and gets a list of representatives (municipal, state, federal) with AI-researched summaries. No auth, no database, no caching.

## Commands

### Backend
```bash
cd backend
source venv/bin/activate        # venv already created
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

**Backend (FastAPI, Python 3.9+):** Single endpoint `POST /api/representatives`.

Request flow:
1. `routers/representatives.py` receives address → calls `services/civic.py`
2. `services/civic.py` calls Google Civic Information API, maps offices to `federal`/`state`/`municipal` levels, returns list of `Representative` models
3. `routers/representatives.py` fans out `services/research.py` for all reps concurrently via `asyncio.gather`
4. `services/research.py` runs a Claude agent (claude-sonnet-4-20250514) with a Tavily `web_search` tool in an agentic loop (up to 5 iterations) to produce a 2-3 paragraph summary per rep
5. Results are sorted by level priority and returned

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

Required in `.env` at project root (see `.env.example`):
- `ANTHROPIC_API_KEY`
- `TAVILY_API_KEY`
- `GOOGLE_CIVIC_API_KEY`

Backend loads these via `python-dotenv` at startup.
