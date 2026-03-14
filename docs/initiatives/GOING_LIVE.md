# Going Live — Deployment Checklist

Deploy MyReps to Google Cloud Run. Using default `*.run.app` URLs (custom domain can be added later).
All steps use the **Google Cloud Console UI** unless noted otherwise.

**Project:** `my-representatives-489301` | **Region:** `us-east1`

---

## 1. Set up Google Cloud project ✅

Created project `my-representatives-489301`, enabled Cloud Run, Secret Manager, and Artifact Registry APIs.

## 2. Store secrets in Secret Manager ✅

Stored via Console: `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `CICERO_API_KEY`, `US_CONGRESS_API_KEY`, `GOOGLE_CIVIC_API_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`.

Granted the default compute service account (`968920716189-compute@developer.gserviceaccount.com`) the `secretmanager.secretAccessor` role on each secret (done via CLI).

## 3. Deploy the backend to Cloud Run ✅ (building)

In Console: **Cloud Run → Create Service → Connect repository**

- Connected GitHub repo, set to deploy from `main` branch
- **Cloud Build** provider, Dockerfile path: `backend/Dockerfile`, build context: `backend/`
- **Authentication:** Allow public access
- **Billing:** Request-based
- **Scaling:** Auto, min 0
- **Ingress:** All
- **Env vars:** `CLAUDE_MODEL=claude-sonnet-4-6`, `RESEARCH_MAX_TOKENS=32768`, `LANGFUSE_BASE_URL=https://us.cloud.langfuse.com`, `US_CONGRESS_REPS_ONLY=false`
- **Secrets** (exposed as env vars, version `latest`): `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `CICERO_API_KEY`, `US_CONGRESS_API_KEY`, `GOOGLE_CIVIC_API_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`

Backend URL: `https://my-representatives-xxxxx-ue.a.run.app` ← update once deployed

## 5. Deploy the frontend to Cloud Run

The frontend Dockerfile is a multi-stage build: Node builds the app, nginx serves the static files.
`VITE_API_URL` is baked in at build time.

In Console: **Cloud Run → Create Service → Connect repository**

- Same GitHub repo, deploy from `main` branch
- Dockerfile path: `frontend/Dockerfile`, build context: `frontend/`
- **Authentication:** Allow public access
- **Billing:** Request-based
- **Scaling:** Auto, min 0
- **Ingress:** All
- **Env vars (build-time):** Need to pass `VITE_API_URL` as a build arg pointing to the backend URL from step 4. In Cloud Build config, add a substitution variable or use `--build-arg` in the build trigger settings.

Frontend URL: `https://myreps-web-xxxxx-ue.a.run.app` ← update once deployed

## 6. Update backend CORS with the frontend URL

In Console: **Cloud Run → backend service → Edit & Deploy New Revision**

- Add/update env var: `CORS_ORIGINS=<frontend URL from step 5>`

## 7. Test end-to-end

- Test with a few real addresses across different states
- Verify all API integrations work with production keys
- Check mobile responsiveness
- Confirm error states display properly (bad address, API failures)
- Verify SSE streaming works (research results appear one-by-one)

## 8. Optional: Custom domain

In Console: **Cloud Run → Domain Mappings** — map your domain to each service. Cloud Run provisions TLS certs automatically. Then update the CORS env var on the backend to match the custom frontend domain.

## 9. Optional improvements

- **Monitoring**: Cloud Logging already captures stdout/stderr. Add an uptime check for the frontend URL.
- **Caching**: Memorystore (managed Redis) to cache research results and reduce API costs
- **Analytics**: Privacy-respecting analytics (Plausible, Umami) to understand usage
- **SEO/social meta tags**: `<meta>` tags and Open Graph image for shareability
- **Cloud CDN**: Load balancer + CDN in front of the frontend for faster global delivery
