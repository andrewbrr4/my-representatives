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
| **Google Cloud** | Cloud Run (backend + frontend), Artifact Registry, networking | Subscription / usage-based | GCP BigQuery Billing Export — auto-exports detailed daily costs by service and SKU to a BigQuery dataset | Fully automatable via scheduled BigQuery query |
| **US Congress API** | Federal representative lookups | Free | N/A — no cost | N/A |
| **Census Geocoder** | Address → congressional district geocoding | Free | N/A — no cost | N/A |

### Cicero credit model
Cicero is purchased in bulk and topped up as needed rather than billed per request. It is represented in the ledger as periodic lump outflows (`source: cicero`, `billing_model: bulk`) logged manually at each top-up. No per-request cost is attributed to Cicero — it appears as an operational expense on the dashboard alongside granular per-request costs from other sources. The running balance remains accurate regardless of billing model.

If usage patterns eventually make amortized per-request attribution useful (e.g. cost-per-lookup calculations), a credit burn rate can be estimated from historical top-up frequency and request volume.

### Ledger schema (phase 2)
```
transactions
  - id
  - type           (inflow | outflow)
  - source         (string — e.g. github_sponsors, anthropic, tavily, cicero, hosting, other)
  - billing_model  (per_request | bulk | subscription)
  - amount_usd
  - description
  - created_at
  - balance_after  (running total)
```

`source` is a freeform string and `billing_model` documents how the cost accrues, so new sources with different billing patterns can be added without a schema migration.

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

### Phase 2 — Database ledger + transparency dashboard

Introduce a `transactions` table and populate it by polling the Langfuse API, so the app owns its cost data independently.

**Langfuse API as data source:**

Langfuse exposes a `GET /api/public/metrics/daily` endpoint that returns aggregated daily metrics including trace counts, total costs, and per-model token usage. A background job (cron or scheduled task) can poll this endpoint and write cost entries to the `transactions` table.

```
GET /api/public/metrics/daily?traceName=research-pipeline
→ { date, countTraces, totalCost, usage: [{ model, inputUsage, outputUsage, totalUsage }] }
```

Langfuse also has per-trace APIs (`GET /api/public/traces`, `GET /api/public/observations`) for more granular per-lookup attribution if needed.

**Implementation approach:**
- Scheduled job (e.g. daily cron) polls `GET /api/public/metrics/daily` for Anthropic costs
- Writes one `transactions` row per day per source (`source: anthropic`, `billing_model: per_request`)
- Tavily costs estimated from trace count × fixed per-search cost (based on plan tier), or from Tavily's own usage dashboard if they add an API
- GCP hosting costs pulled from BigQuery Billing Export via scheduled query, written as daily `transactions` rows (`source: gcp`, `billing_model: subscription`)
- Bulk costs (Cicero) written via a simple admin endpoint called manually on each top-up
- `transactions` table per schema above

**Endpoints and dashboard:**
- `/api/costs/summary` and `/api/costs/transactions` backend endpoints
- `/costs` frontend dashboard: daily spend by source, period totals, average cost per lookup, inflows vs. outflows once donation infrastructure exists

Cicero and other bulk sources appear as periodic lump entries alongside granular per-request costs.