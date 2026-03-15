# Infrastructure

MyReps runs on Google Cloud Platform (GCP) in the `us-east1` region.

## Services

### Cloud Run — Backend (`my-reps-backend`)
- **Image:** Built from `backend/Dockerfile` (Python 3.12-slim, uvicorn, 2 workers)
- **Port:** 8080
- **Region:** us-east1
- **VPC:** Direct VPC egress to `default` network (required for Redis access)
- **Traffic routing:** Route only private IPs to VPC
- **Secrets:** API keys injected via GCP Secret Manager (see below)
- **Env vars:** `REDIS_URL=redis://10.107.77.182:6379` set as a Cloud Run env var (not a secret — it's a private IP)

### Cloud Run — Frontend (`my-reps-frontend`)
- **Image:** Built from `frontend/Dockerfile` (Node 22 build → Nginx)
- **Port:** 8080
- **Build args:** `VITE_API_URL` (backend Cloud Run URL), `VITE_GOOGLE_PLACES_API_KEY`

### Memorystore for Redis
- **Purpose:** Persistent rep research cache (24h TTL) and job store shared across backend workers
- **Instance:** Basic tier, `us-east1`
- **Primary endpoint:** `10.107.77.182:6379` (private IP, only reachable from same VPC)
- **Read endpoint:** `10.107.77.181:6379`
- **Network:** `default` (`my-representatives-489301`), direct peering
- **IP range:** `10.107.77.176/28`

## Secrets (GCP Secret Manager)

API keys are stored in Secret Manager and mounted as env vars in Cloud Run, not baked into images or stored in `.env` in production.

| Secret name | Env var | Used by |
|------------|---------|---------|
| `ANTHROPIC_API_KEY` | `ANTHROPIC_API_KEY` | Backend — LLM research agents |
| `TAVILY_API_KEY` | `TAVILY_API_KEY` | Backend — web search tool |
| `CICERO_API_KEY` | `CICERO_API_KEY` | Backend — state/municipal rep lookups |
| `US_CONGRESS_API_KEY` | `US_CONGRESS_API_KEY` | Backend — federal rep lookups |
| `LANGFUSE_SECRET_KEY` | `LANGFUSE_SECRET_KEY` | Backend — tracing |
| `LANGFUSE_PUBLIC_KEY` | `LANGFUSE_PUBLIC_KEY` | Backend — tracing |

Non-secret env vars (set directly on Cloud Run):
- `REDIS_URL` — Redis connection string
- `CLAUDE_MODEL` — model ID for research agents
- `RESEARCH_MAX_TOKENS` — max tokens per section agent
- `LANGFUSE_BASE_URL` — Langfuse endpoint
- `US_CONGRESS_REPS_ONLY` — feature flag
- `REP_CACHE_TTL_SECONDS` — cache TTL (default 86400)
- `JOB_TTL_SECONDS` — job TTL (default 1800)

## Networking

```
Internet → Cloud Run (frontend) → Cloud Run (backend) → Memorystore Redis
                                                      → External APIs (Anthropic, Tavily, Cicero, Congress, Census)
```

Cloud Run backend connects to Redis via Direct VPC egress on the `default` network. Only traffic to private IPs is routed through the VPC; external API calls go directly over the internet.

## Local Development

Local dev does **not** use Redis. When `REDIS_URL` is absent:
- Job store: in-memory (works for single-worker `--reload` mode)
- Rep cache: disabled (no caching — every lookup does fresh research)

```bash
# No REDIS_URL needed locally
conda activate my-reps
cd backend && uvicorn main:app --reload     # :8000
cd frontend && npm run dev                  # :5173
```

## Deploying

Images are built and pushed to Artifact Registry, then deployed to Cloud Run.

```bash
# Backend
docker build -t us-east1-docker.pkg.dev/<PROJECT_ID>/my-reps/backend ./backend
docker push us-east1-docker.pkg.dev/<PROJECT_ID>/my-reps/backend
gcloud run deploy my-reps-backend --image us-east1-docker.pkg.dev/<PROJECT_ID>/my-reps/backend --region us-east1

# Frontend
docker build -t us-east1-docker.pkg.dev/<PROJECT_ID>/my-reps/frontend \
  --build-arg VITE_API_URL=<BACKEND_URL> \
  --build-arg VITE_GOOGLE_PLACES_API_KEY=<KEY> \
  ./frontend
docker push us-east1-docker.pkg.dev/<PROJECT_ID>/my-reps/frontend
gcloud run deploy my-reps-frontend --image us-east1-docker.pkg.dev/<PROJECT_ID>/my-reps/frontend --region us-east1
```
