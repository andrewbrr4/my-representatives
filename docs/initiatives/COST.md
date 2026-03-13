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

**Outflows (API costs) — partially automatable:**
- Anthropic — tracked automatically via Langfuse callback
- Tavily — cost per request captured from API responses and attached as Langfuse trace metadata
- Cicero — bulk credit model (see below); logged as manual outflow entries on each top-up
- Hosting (Render, Fly, etc.) — most have APIs or invoices you can parse. Less clean but doable.
- New cost sources should be added here as the stack grows.

**What stays manual:** Cicero top-ups, hosting invoices if the provider has no API, and any one-off expenses.

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

### Phase 1 — Langfuse as source of truth (operator visibility only)
Langfuse already captures Anthropic costs automatically via the callback. The only change needed is attaching Tavily costs to each trace as metadata so total per-request cost is visible in the Langfuse dashboard.

- After each Tavily call, extract the cost from the API response
- Attach it as metadata on the parent Langfuse trace for that request
- Each subagent trace is a child span under a parent request trace, so cost rolls up at the request level in Langfuse

No database, no frontend dashboard, no new endpoints. This is purely for your own visibility while the app is in early use.

### Phase 2 — Database ledger + transparency dashboard
Introduce a `transactions` table and move cost tracking out of Langfuse into the app's own database. Langfuse remains for observability; the ledger becomes the source of truth for costs and donations.

- `transactions` table per schema above
- Per-request costs (Anthropic + Tavily) written at the end of each lookup pipeline run
- Bulk costs (Cicero, hosting) written via a simple admin endpoint called manually on each top-up
- `/api/costs/summary` and `/api/costs/traces` backend endpoints
- `/costs` frontend dashboard: daily spend by source, period totals, average cost per lookup, inflows vs. outflows once donation infrastructure exists

Cicero and other bulk sources appear as periodic lump entries alongside granular per-request costs.