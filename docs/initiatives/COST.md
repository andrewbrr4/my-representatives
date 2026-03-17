# Cost Tracking & Transparency

## Problem
MyReps makes API calls (Anthropic, Tavily, Cicero) on every lookup. Without visibility into what those cost, there's no way to set budgets, catch runaway spend, or eventually let users see where money goes.

## Vision: crowdfunded transparency
A transparent, crowdfunded wallet where users can contribute to cover MyReps' API/hosting costs and see exactly where money goes, but only you control spending.

**Architecture:** Contributions → payment processor → bank account → dedicated card → API billers, with a public transparency ledger.

### What we explored
- **Stripe + Mercury bank + virtual card** was the cleanest technical path
- **Nonprofit (501(c)(3))** would enable tax-deductible donations but takes 6-12 months to file
- **Fiscal sponsorship (Open Collective)** would have been ideal but OCF shut down in 2024
- Other fiscal sponsors exist but are selective or niche fits

### Where we landed
Tabled for now. The legal/banking infrastructure is too much overhead pre-launch. Revisit when there are real users and real costs.

**When we come back to it, the likely path is:**
- GitHub Sponsors as the immediate lightweight option (zero fees, fits the open source civic tech vibe)
- In-app transparency ledger (or public Google Sheet as MVP)
- Proper nonprofit incorporation only when donation volume justifies it

### How automation breaks down

**Inflows (donations) — fully automatable:**
GitHub Sponsors has a webhook that fires on each new sponsorship. Stripe has webhooks too. Catch those in a FastAPI endpoint and write to the ledger table automatically.

**Outflows (API + hosting costs) — see cost sources table below for full breakdown.**

**What stays manual:** Cicero top-ups and any one-off expenses.

### Cost sources

| Source | What it covers | Billing model | Tracking method | Automation |
|--------|---------------|---------------|-----------------|------------|
| **Anthropic** | LLM calls for research agents (Claude) | Per-request (tokens) | Langfuse `GET /api/public/metrics/daily` — captures token counts and USD cost automatically via `CallbackHandler` | Fully automatable via scheduled Langfuse API poll |
| **Tavily** | Web search tool calls during research | Per-request (searches) | Langfuse traces record each `web_search` tool call as a span; cost estimated from search count × plan tier rate | Automatable — count from Langfuse, multiply by known rate |
| **Cicero** | State + municipal representative lookups | Bulk credits (pre-purchased) | Manual log entry on each top-up | Manual — bulk purchase model, no per-request cost attribution |
| **Google Cloud** | Cloud Run (backend + frontend), Artifact Registry, networking | Subscription / usage-based | GCP Cloud Billing API (`cloudbilling.googleapis.com`) — query cost and usage data by service and SKU without needing a data warehouse | Automatable via scheduled API call |
| **US Congress API** | Federal representative lookups | Free | N/A — no cost | N/A |
| **Census Geocoder** | Address → congressional district geocoding | Free | N/A — no cost | N/A |

### Cicero credit model
Cicero is purchased in bulk and topped up as needed rather than billed per request. It is represented in the ledger as periodic lump outflows (`source: cicero`, `billing_model: bulk`) logged manually at each top-up. No per-request cost is attributed to Cicero — it appears as an operational expense on the dashboard alongside granular per-request costs from other sources. The running balance remains accurate regardless of billing model.

If usage patterns eventually make amortized per-request attribution useful (e.g. cost-per-lookup calculations), a credit burn rate can be estimated from historical top-up frequency and request volume.

### Database schema (implemented)

Two tables in Cloud SQL PostgreSQL. Migration: `backend/migrations/001_create_jobs_and_transactions.sql`.

```
jobs
  - id              text PK (12-char hex job_id)
  - address         text
  - reps_found      int
  - reps_researched int (reps that hit the pipeline, not cached)
  - reps_cached     int
  - input_tokens    int
  - output_tokens   int
  - tool_calls      int
  - status          text (done | error)
  - created_at      timestamptz

transactions
  - id              serial PK
  - type            text (inflow | outflow)
  - source          text (e.g. github_sponsors, anthropic, tavily, cicero, gcp)
  - billing_model   text (per_request | bulk | subscription)
  - amount_usd      numeric(10,4)
  - description     text
  - job_id          text FK → jobs(id), nullable
  - created_at      timestamptz
  - balance_after   numeric(10,4) (running total)
```

`jobs` captures per-request operational telemetry. `transactions` is the financial ledger. `job_id` FK links per-request outflows to specific lookups; null for bulk/subscription/inflow entries. `source` is freeform so new cost sources can be added without a schema migration.

---

## Phases

### Phase 1 — Langfuse as source of truth (no app code changes)

Langfuse already captures Anthropic token usage and costs automatically via the `CallbackHandler` passed to each LangChain agent. Tavily call counts are also visible in Langfuse as tool call spans within each agent trace. No application code changes are needed for operator visibility — the Langfuse dashboard already shows per-trace token usage, cost, and tool call counts.

**What Langfuse tracks today (zero additional work):**
- Anthropic input/output tokens and USD cost per LLM call (via `ChatAnthropic` + `CallbackHandler`)
- Tool call spans (each `web_search` invocation appears as a child span)
- Trace hierarchy: each representative's research is an `@observe`-decorated trace with 5 section-agent child spans

**What Langfuse does NOT track automatically:**
- Tavily dollar cost (Tavily doesn't return cost in its API response; cost is based on plan tier)
- Cicero costs (bulk credit model, not per-request)

This phase requires no code changes. Use the Langfuse dashboard for ad-hoc cost visibility during early usage.

### Phase 1.5 — Per-request usage tracking + persistence (implemented)

A custom `UsageTracker` callback handler (`research/usage.py`) runs alongside the Langfuse handler on every section agent, tracking input tokens, output tokens, and tool calls independently. Fully decoupled from Langfuse — if Langfuse breaks, usage tracking still works.

Usage bubbles up from section → rep → job:
- Each section agent returns its `UsageStats` alongside content/citations
- `research_representative()` aggregates across 7 sections and logs per-rep totals
- `_run_all_research()` aggregates across all reps and logs the job-level summary:

```
Job abc123: research complete — 8 reps (2 cached, 6 researched) — 45,231 input tokens, 12,847 output tokens, 58,078 total tokens, 42 tool calls
```

**Database persistence:** After logging, usage data is written to the `jobs` table in Cloud SQL PostgreSQL via `db.py` (asyncpg connection pool). DB writes are wrapped in try/except so failures never break the main research flow.

**Database:** Cloud SQL for PostgreSQL (GCP-managed). Connection via `DATABASE_URL` env var. Schema migrations in `backend/migrations/`.

### Phase 2 — Transactions ledger + transparency dashboard

Database and `jobs` table are live. `jobs` rows are written automatically on every research completion. What remains:

**Populate `transactions` table:**
- Write Anthropic cost entries derived from `jobs` data (token counts × per-token pricing)
- Tavily costs estimated from `tool_calls` count × per-search cost (based on plan tier)
- GCP hosting costs from Cloud Billing API, written as periodic entries (`source: gcp`, `billing_model: subscription`)
- Bulk costs (Cicero) written via a simple admin endpoint called manually on each top-up

**Endpoints and dashboard:**
- `/api/costs/summary` and `/api/costs/transactions` backend endpoints
- `/costs` frontend dashboard: daily spend by source, period totals, average cost per lookup, inflows vs. outflows once donation infrastructure exists

Cicero and other bulk sources appear as periodic lump entries alongside granular per-request costs.