# Tasks

## Going Live
- [ ] Create GCP project, enable Cloud Run + Secret Manager + Artifact Registry
- [ ] Store API keys in Secret Manager, grant service account access
- [ ] Deploy backend to Cloud Run with secrets wired up
- [ ] Build frontend with production API URL, deploy to Cloud Run
- [ ] Map custom domain, add DNS records, update CORS
- [ ] Set up uptime check + error alerting
- [ ] E2E test: real addresses, mobile, error states, rate limiting

## Cost Tracking (Phase 1)
- [ ] Extract Tavily cost from API response after each call
- [ ] Attach Tavily cost as metadata on parent Langfuse trace
- [ ] Verify per-request cost rollup in Langfuse dashboard

## Feedback (Phase 1)
- [ ] Pick a database provider (first DB in the project)
- [ ] Create `feedback` table per schema in FEEDBACK.md
- [ ] Build `POST /api/feedback` endpoint
- [ ] Build `/feedback` page (type toggle + free text)
- [ ] Link from results page with rep/request context pre-populated
