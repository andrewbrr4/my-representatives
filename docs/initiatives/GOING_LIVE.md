# Going Live — Deployment Checklist

Remaining steps to take MyReps from local dev to a production deployment on Google Cloud.

---

## 1. Set up Google Cloud project

```bash
gcloud projects create myreps --name="MyReps"
gcloud config set project myreps
gcloud services enable run.googleapis.com secretmanager.googleapis.com artifactregistry.googleapis.com
```

## 2. Store API keys in Secret Manager

```bash
echo -n "YOUR_KEY" | gcloud secrets create ANTHROPIC_API_KEY --data-file=-
echo -n "YOUR_KEY" | gcloud secrets create TAVILY_API_KEY --data-file=-
echo -n "YOUR_KEY" | gcloud secrets create CICERO_API_KEY --data-file=-
echo -n "YOUR_KEY" | gcloud secrets create US_CONGRESS_API_KEY --data-file=-
echo -n "YOUR_KEY" | gcloud secrets create GOOGLE_CIVIC_API_KEY --data-file=-
```

Grant the Cloud Run service account access:

```bash
PROJECT_NUM=$(gcloud projects describe myreps --format='value(projectNumber)')
gcloud secrets add-iam-policy-binding ANTHROPIC_API_KEY \
  --member="serviceAccount:${PROJECT_NUM}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
# Repeat for each secret
```

## 3. Deploy the backend to Cloud Run

Create an Artifact Registry repo for Docker images:

```bash
gcloud artifacts repositories create myreps --repository-format=docker --location=us-central1
```

Build and deploy:

```bash
cd backend
gcloud run deploy myreps-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-secrets="ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest,TAVILY_API_KEY=TAVILY_API_KEY:latest,CICERO_API_KEY=CICERO_API_KEY:latest,US_CONGRESS_API_KEY=US_CONGRESS_API_KEY:latest,GOOGLE_CIVIC_API_KEY=GOOGLE_CIVIC_API_KEY:latest" \
  --set-env-vars="CORS_ORIGINS=https://myreps.yourdomain.com"
```

Note the service URL from the output (e.g., `https://myreps-api-xxxxx-uc.a.run.app`).

## 4. Build and deploy the frontend to Cloud Run

```bash
cd frontend
VITE_API_URL=https://myreps-api-xxxxx-uc.a.run.app npm run build
```

Then deploy the nginx-based Dockerfile:

```bash
gcloud run deploy myreps-web \
  --source . \
  --region us-central1 \
  --allow-unauthenticated
```

## 5. Set up a custom domain

Map your domain to the Cloud Run services:

```bash
gcloud run domain-mappings create --service myreps-web --domain myreps.yourdomain.com --region us-central1
gcloud run domain-mappings create --service myreps-api --domain api.myreps.yourdomain.com --region us-central1
```

Add the DNS records shown in the output to your domain registrar. Cloud Run provisions TLS certificates automatically.

After DNS is live, update the backend's CORS setting:

```bash
gcloud run services update myreps-api --region us-central1 \
  --set-env-vars="CORS_ORIGINS=https://myreps.yourdomain.com"
```

## 6. Set up monitoring

Use Google Cloud's built-in tools:

- **Cloud Logging** — already captures stdout/stderr from Cloud Run (your existing request logging middleware works out of the box)
- **Cloud Monitoring** — set up an uptime check for your frontend URL and an alerting policy for error rate spikes
- **Error Reporting** — automatically groups and tracks errors from Cloud Run services

```bash
gcloud monitoring uptime create myreps-uptime \
  --display-name="MyReps Frontend" \
  --uri=https://myreps.yourdomain.com \
  --period=5
```

## 7. Test end-to-end before launch

- Test with a few real addresses across different states
- Verify all API integrations work with production keys
- Check mobile responsiveness
- Confirm error states display properly (bad address, API failures)
- Verify rate limiting works (10 req/min per IP)

## 8. Optional improvements

These aren't blockers but are worth considering:

- **Caching**: Use Memorystore (managed Redis) to cache research results and reduce API costs
- **Error tracking**: Cloud Error Reporting covers this, or add Sentry for richer frontend error context
- **Analytics**: Simple, privacy-respecting analytics (Plausible, Umami) to understand usage
- **SEO/social meta tags**: Add `<meta>` tags and an Open Graph image if you want the site to be shareable
- **Cloud CDN**: Put a load balancer + Cloud CDN in front of the frontend for faster global delivery
