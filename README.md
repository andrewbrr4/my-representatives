# MyReps

Find your elected representatives at every level of government — federal, state, and municipal — with AI-researched summaries for each.

- [Product mission & principles](./docs/MISSION.md)
- [Design approach & challenges](./docs/DESIGN.md)

## How It Works

1. Enter your address
2. The backend calls the Cicero API to find your elected representatives at all levels
3. For each rep, a Claude AI agent searches the web (via Tavily) and writes a nonpartisan summary
4. Results are displayed grouped by government level

## API Keys You'll Need

| Key | Where to get it |
|-----|----------------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) |
| `TAVILY_API_KEY` | [tavily.com](https://tavily.com/) — free tier available |
| `CICERO_API_KEY` | [cicerodata.com](https://www.cicerodata.com/) — comprehensive elected official data |
| `GOOGLE_CIVIC_API_KEY` | [Google Cloud Console](https://console.cloud.google.com/apis/library/civicinfo.googleapis.com) — for election/ballot data |

## Setup

### Run with Docker Compose

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000

### Run locally (without Docker)

**Backend:**
```bash
conda create -n my-reps python=3.13 -y
conda activate my-reps
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Tech Stack

- **Frontend:** React + TypeScript + Vite + Tailwind CSS + shadcn/ui
- **Backend:** FastAPI (Python)
- **LLM:** Anthropic Claude (claude-sonnet-4-20250514) with tool use
- **Web Search:** Tavily API
- **Representative Data:** Cicero API
- **Election Data:** Google Civic Information API (voterinfo/elections endpoints)
