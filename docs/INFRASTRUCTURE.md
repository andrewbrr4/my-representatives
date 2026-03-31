# Infrastructure

MyReps runs on Google Cloud Platform (GCP) in the `us-east1` region. Production URL: **https://knowmyreps.org**

## Services

### Cloud Run — Backend (`my-reps-backend`)
- **Image:** Built from `backend/Dockerfile` (Python 3.13-slim, uvicorn, 1 worker)
- **Port:** 8080
- **Region:** us-east1
- **Domain:** `api.knowmyreps.org`
- **VPC:** Direct VPC egress to `default` network (required for Redis access)
- **Traffic routing:** Route only private IPs to VPC
- **Cloud SQL connection:** Add the Cloud SQL instance (`my-representatives-489301:us-central1:my-representatives`) to the service. Cloud Run injects a proxy sidecar that exposes a Unix socket at `/cloudsql/my-representatives-489301:us-central1:my-representatives`. The backend connects via `DB_SOCKET_PATH` env var (see below).
- **Secrets:** API keys injected via GCP Secret Manager (see below)
- **Env vars:** `REDIS_URL=redis://10.107.77.182:6379` set as a Cloud Run env var (not a secret — it's a private IP)

### Cloud Run — Frontend (`my-reps-frontend`)
- **Image:** Built from `frontend/Dockerfile` (Node 22 build → Nginx)
- **Port:** 8080
- **Domain:** `knowmyreps.org`
- **Build args:** `VITE_API_URL` (backend URL, e.g. `https://api.knowmyreps.org`), `VITE_GOOGLE_PLACES_API_KEY`

### Memorystore for Redis
- **Purpose:** Persistent rep research cache (3-day TTL) shared across backend workers
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
| `GOOGLE_CIVIC_API_KEY` | `GOOGLE_CIVIC_API_KEY` | Backend — election/ballot data via Civic Information API |
| `LANGFUSE_SECRET_KEY` | `LANGFUSE_SECRET_KEY` | Backend — tracing |
| `LANGFUSE_PUBLIC_KEY` | `LANGFUSE_PUBLIC_KEY` | Backend — tracing |

Non-secret env vars (set directly on Cloud Run):
- `REDIS_URL` — Redis connection string
- `DB_SOCKET_PATH` — Cloud SQL Unix socket path (e.g. `/cloudsql/my-representatives-489301:us-central1:my-representatives`)
- `DB_NAME` — Postgres database name (default `postgres`)
- `DB_USER` — Postgres user (default `postgres`)
- `CLAUDE_MODEL` — model ID for research agents
- `RESEARCH_MAX_TOKENS` — max tokens per section agent
- `LANGFUSE_BASE_URL` — Langfuse endpoint
- `REP_CACHE_TTL_SECONDS` — cache TTL (default 259200 / 3 days)
- `JOB_TTL_SECONDS` — research task TTL (default 1800)
- `ANTHROPIC_INPUT_COST_PER_M` — USD per million input tokens (cost tracking)
- `ANTHROPIC_OUTPUT_COST_PER_M` — USD per million output tokens (cost tracking)
- `COST_PER_SEARCH` — USD per Tavily search (cost tracking)
- `SEARCH_TOOL` — search provider name (default `tavily`)
- `ENVIRONMENT` — `dev` or `prod` (recorded in research_tasks)

| Secret name | Env var | Used by |
|------------|---------|---------|
| `DB_PASSWORD` | `DB_PASSWORD` | Backend — Cloud SQL password (used with `DB_SOCKET_PATH`) |

## Custom Domain

- **Domain:** `knowmyreps.org` (registered via Google Cloud Domains)
- **DNS:** Managed in Cloud DNS (zone: `knowmyreps-org`)
- **Frontend:** `knowmyreps.org` → Cloud Run `my-reps-frontend` (A + AAAA records)
- **Backend API:** `api.knowmyreps.org` → Cloud Run `my-reps-backend` (CNAME → `ghs.googlehosted.com.`)
- **SSL:** Managed automatically by Cloud Run domain mappings

## Networking

```
Internet → knowmyreps.org (Cloud Run frontend) → api.knowmyreps.org (Cloud Run backend) → Memorystore Redis
                                                                                         → Cloud SQL PostgreSQL
                                                                                         → External APIs (Anthropic, Tavily, Cicero, Congress, Census, Google Civic)
```

Cloud Run backend connects to Redis via Direct VPC egress on the `default` network. Only traffic to private IPs is routed through the VPC; external API calls go directly over the internet.

### Cloud SQL for PostgreSQL
- **Purpose:** Persists research usage data (`research_tasks`), financial ledger (`transactions`), and future tables (feedback, etc.)
- **Instance:** `my-representatives-489301:us-central1:my-representatives`
- **Region:** us-central1
- **Connection from Cloud Run:** Cloud SQL proxy sidecar → Unix socket at `/cloudsql/my-representatives-489301:us-central1:my-representatives`
- **Connection from local dev:** Cloud SQL Auth Proxy → `localhost:5432`

## Local Development

Local dev does **not** use Redis. When `REDIS_URL` is absent:
- Research task store: in-memory (works for single-worker `--reload` mode)
- Rep cache: disabled (no caching — every research request runs fresh)

### Cloud SQL Auth Proxy

Local dev connects to Cloud SQL via the Auth Proxy (authenticates with your `gcloud` IAM credentials — no public IP or IP allowlisting needed).

```bash
# Start the proxy (runs in background, proxies localhost:5432 → Cloud SQL)
cloud-sql-proxy my-representatives-489301:us-central1:my-representatives --port 5432 &
```

`.env` should use `127.0.0.1` as the host:
```
DATABASE_URL=postgresql://postgres:<password>@127.0.0.1:5432/postgres
```

### Running locally

```bash
conda activate my-reps

# Start Cloud SQL proxy
cloud-sql-proxy my-representatives-489301:us-central1:my-representatives --port 5432 &

# Backend + frontend
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
  --build-arg VITE_API_URL=https://api.knowmyreps.org \
  --build-arg VITE_GOOGLE_PLACES_API_KEY=<KEY> \
  ./frontend
docker push us-east1-docker.pkg.dev/<PROJECT_ID>/my-reps/frontend
gcloud run deploy my-reps-frontend --image us-east1-docker.pkg.dev/<PROJECT_ID>/my-reps/frontend --region us-east1
```
