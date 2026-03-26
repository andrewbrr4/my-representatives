# Tasks

## Feedback
* Create survey for feedback (3rd party tool)
* Link to website results page

## Cost Tracing
* Enable GCP BigQuery Billing Export for automated hosting cost tracking
* Build scheduled job to poll Langfuse API (`GET /api/public/metrics/daily`) for Anthropic costs
* Estimate Tavily costs from Langfuse tool call span counts × plan tier rate
* Build scheduled job to query BigQuery Billing Export for GCP costs
* Build admin endpoint for manual Cicero top-up entries
* Build `/api/costs/summary` and `/api/costs/transactions` endpoints
* Build `/costs` frontend dashboard

## Elections
* Evaluate alternatives to Google Civic API for election data (see [ELECTIONS_API_ALTERNATIVES.md](./initiatives/ELECTIONS_API_ALTERNATIVES.md))
* Handle Google Civic `voterinfo` 400 errors more gracefully (currently uses two-step discovery workaround)
* Add election research caching to Redis (currently in-memory only between deploys)
