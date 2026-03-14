# Tasks

## Feedback
* Create survey for feedback (3rd party tool)
* Link to website results page

## Cost Tracing
* Enable GCP BigQuery Billing Export for automated hosting cost tracking
* Build scheduled job to poll Langfuse API (`GET /api/public/metrics/daily`) for Anthropic costs
* Estimate Tavily costs from Langfuse tool call span counts × plan tier rate
* Build scheduled job to query BigQuery Billing Export for GCP costs
* Write polled costs to `transactions` table (Phase 2 of COST.md)
* Build admin endpoint for manual Cicero top-up entries
* Build `/api/costs/summary` and `/api/costs/transactions` endpoints
* Build `/costs` frontend dashboard
