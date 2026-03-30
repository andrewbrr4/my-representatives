# Performance Audit

Last updated: 2026-03-28

This is a living document tracking performance bottlenecks, their severity, and remediation status.

---

## TL;DR — Where the Time Goes

When a user opens the app on mobile and enters an address, here's the latency breakdown:

```
[Mobile user taps search]
  │
  ├─ Cold start (if instance scaled to zero): ~4-8s  ✅ FIXED (min instances = 1)
  │    └─ Python imports: LangChain, LangGraph, Langfuse, Anthropic SDK
  │
  ├─ POST /api/representatives: ~1.5-2.5s
  │    ├─ asyncio.gather (parallel):
  │    │    ├─ Congress path (sequential chain):
  │    │    │    ├─ Census Geocoder HTTP:        ~300-600ms
  │    │    │    ├─ Congress API list members:    ~300-500ms
  │    │    │    └─ Detail fetch x3 PARALLEL:     ~200-400ms   ✅ FIXED
  │    │    │
  │    │    └─ Cicero path:
  │    │         ├─ Cicero API call:             ~400-800ms
  │    │         └─ (conditional 2nd call):      ~400-800ms  ← SOMETIMES
  │    │
  │    └─ Total = max(congress_path, cicero_path) ≈ 0.8-1.5s (post-fix)
  │
  ├─ Frontend JS bundle (no code splitting): single chunk, all routes
  │
  └─ No CDN — assets served from Cloud Run us-east1 only
```

---

## Critical Issues

### ~~1. Cloud Run Cold Start (~4-8s)~~ ✅ FIXED 2026-03-28

**Fix applied:** Set Cloud Run min instances = 1 via GCP console. Eliminates cold start for users.

**Remaining opportunity:** Lazy-import heavy packages (LangChain, LangGraph, Langfuse) to reduce restart/deploy cold start. Low priority now that min instances is set.

---

### ~~2. Congress API Detail Fetches Are Sequential (~600-1200ms wasted)~~ ✅ FIXED 2026-03-28

**Fix applied:** Replaced sequential `for` loop with `asyncio.gather` in `backend/services/congress.py`. 3 detail fetches now run concurrently.

**Estimated savings:** 400-800ms per lookup.

---

### 3. No CDN for Frontend

**Impact:** Static assets (HTML, JS, CSS) served directly from Cloud Run in `us-east1`. Users outside the eastern US get higher TTFB.

**Root cause:** No Cloud CDN, Firebase Hosting, or Cloudflare in front of the frontend service.

**Fix options:**
- **Quick:** Add Cloud CDN in front of the frontend Cloud Run service
- **Better:** Move frontend to Firebase Hosting (free tier, global CDN, automatic cache invalidation)
- The nginx config already sets correct cache headers (`max-age=31536000, immutable` for `/assets/`)

---

### 4. Cross-Region Database (us-central1) vs Backend (us-east1)

**Impact:** Every DB write (research task completion) crosses regions, adding ~20-40ms per write.

**Root cause:** Cloud SQL is in `us-central1`, everything else is in `us-east1`.

**Fix:** Migrate Cloud SQL to `us-east1`, or accept the latency since DB writes are not on the critical path (they happen at end of background research tasks).

**Note:** This is low priority since DB writes don't block user-facing requests.

---

### 5. Cicero Double-Call for President/VP

**Impact:** When Cicero doesn't return President/VP for the given address (happens inconsistently), a second full API call is made with the White House address. Doubles Cicero latency when triggered.

**Root cause:** `backend/services/cicero.py:112-118`

**Fix options:**
- Cache President/VP data (it changes at most every 4 years)
- Hardcode current President/VP and skip the lookup entirely
- Accept the inconsistency and just don't show President/VP (are users looking these up?)

---

### 6. Frontend: No Code Splitting

**Impact:** All three pages (Search, Reps, Elections) and all components ship in a single JS chunk. First-time visitors download everything before seeing the search page.

**Root cause:** `frontend/src/App.tsx` — all page imports are static, no `React.lazy()`.

**Fix:**
```tsx
const RepresentativesPage = React.lazy(() => import('./pages/RepresentativesPage'));
const ElectionsPage = React.lazy(() => import('./pages/ElectionsPage'));
```
Plus `build.rollupOptions.output.manualChunks` in `vite.config.ts` for vendor splitting.

---

### 7. Frontend: Global Re-render on Every Poll Tick

**Impact:** During research polling (every 2s), `bumpVersion()` causes ALL rep cards to re-render, even those with no active research.

**Root cause:** `frontend/src/hooks/useResearchQuery.ts:47-56` — global version counter pattern. Every `RepCard` subscribes to the same cache version. `RepCard` is not wrapped in `React.memo`.

**Fix:** Replace global version counter with per-key TanStack Query subscriptions. Each card subscribes to its own `["research", key]` query. Add `React.memo` to `RepCard` and `CandidateCard`.

---

## Significant Issues

### 8. New httpx Client Per Request

**Where:** `congress.py:98`, `cicero.py:104`

Each lookup creates a new `httpx.AsyncClient`, which means no TLS session reuse between requests. A module-level client with connection pooling would eliminate repeated TLS handshakes.

---

### 9. `react-markdown` Installed But Never Used

**Where:** `frontend/package.json`

Dead dependency adding ~50-100KB to the bundle (with unified/remark/rehype chain). Remove it.

---

### 10. `tw-animate-css` Can't Be Tree-Shaken

**Where:** `frontend/src/index.css:2`

Raw CSS import includes ~100 animation classes. Only `animate-pulse` is used. Replace with just the pulse animation or remove the import.

---

### 11. No `loading="lazy"` on Images

**Where:** `RepCard.tsx:182`, `CandidateCard.tsx:33`

All rep/candidate photos fetch eagerly. With 6-10 cards on screen, that's 6-10 concurrent image requests competing with API calls.

---

### 12. Research Prompt Files Read on Every Agent Call

**Where:** `backend/research/pipeline.py:158-163`

14 synchronous file reads per research run (2 files x 7 sections) on the async event loop. `election_pipeline.py` correctly reads prompts at module load time; the rep pipeline should do the same.

---

### 13. `renderInline` Regex Runs on Every Re-render

**Where:** `frontend/src/components/RepCard.tsx:20-60`

Regex splitting runs on all section text every 2 seconds during polling. Should be memoized.

---

### 14. Research Cache `gcTime` Too Short

**Where:** `frontend/src/lib/queryClient.ts`

Default `gcTime` is 5 minutes. Research that took 30-60s to generate gets garbage collected after 5 minutes of navigating away. Should be 30 minutes to match backend `JOB_TTL_SECONDS`.

---

### 15. InMemoryResearchStore Prevents Horizontal Scaling

**Where:** `backend/store/research_store.py`

All research task state lives in a Python dict. Multiple Cloud Run instances would each have their own store — poll requests hitting a different instance than the one running research would fail.

**Current constraint:** Backend must run as max 1 instance, or migrate store to Redis.

---

### 16. No `.dockerignore` Files

**Where:** Both `backend/` and `frontend/`

Test notebooks, `__pycache__`, and potentially `.env` files are sent to Docker build context.

---

### 17. Backend Has No CI/CD

**Where:** Only `frontend/cloudbuild.yaml` exists

Backend deploys are manual `docker build` + `gcloud run deploy`. No automated testing or deployment pipeline.

---

### 18. Frontend Cloud Build Uses `--no-cache`

**Where:** `frontend/cloudbuild.yaml`

Every build re-installs all npm dependencies from scratch. Removing `--no-cache` would let Docker cache the `npm ci` layer.

---

### 19. Cloud Run Config Not in Version Control

Memory, CPU, min/max instances, concurrency, and timeout settings are only in the GCP console. Not reproducible, not auditable.

**Fix:** Add a `service.yaml` or use `gcloud run deploy` flags in a deploy script checked into the repo.

---

## Minor Issues

| Issue | Location | Notes |
|-------|----------|-------|
| Favicon 404s in production | `frontend/index.html:5` | References `/vite.svg` which doesn't exist |
| Page title is "frontend" | `frontend/index.html:8` | Should be "MyReps" |
| Orphaned `react.svg` asset | `frontend/src/assets/react.svg` | Vite boilerplate, never imported |
| Backend Dockerfile uses Python 3.12 | `backend/Dockerfile` | Project targets 3.13+ |
| No image dimensions → layout shift | `RepCard.tsx`, `CandidateCard.tsx` | No `width`/`height` on `<img>` |
| No polling backoff on error | `useResearchQuery.ts:95-97` | Infinite 2s polling if backend is down |
| `model_validate` on every section | `store/research_store.py:68` | 7 Pydantic round-trips per research run |
| Dark mode CSS vars but no toggle | `frontend/src/index.css:84-116` | Dead CSS |
| Research semaphore limits to 2 concurrent | `pipeline.py:33` | By design, but 3rd user waits |

---

## Prioritized Action Plan

### Phase 1: Quick Wins (hours, no architecture changes)

1. ~~**Parallelize Congress detail fetches** — `asyncio.gather` in `congress.py` (~800ms savings)~~ ✅
2. ~~**Set Cloud Run min instances = 1** — eliminates cold start for users (~4-8s savings)~~ ✅
3. **Remove `react-markdown`** from `package.json` (~50-100KB bundle reduction)
4. **Add `React.lazy` for route pages** — code split the three routes
5. **Add `loading="lazy"` to images** — defer offscreen photo loads
6. **Cache prompt files at module load** in `pipeline.py` (match `election_pipeline.py`)
7. **Add `.dockerignore` files** — exclude test files, caches, env files
8. **Fix favicon, page title** — trivial polish

### Phase 2: Moderate Effort (days)

9. **Replace global version counter** with per-key TanStack Query subscriptions + `React.memo`
10. **Reuse httpx clients** — module-level `AsyncClient` with connection pooling
11. **Add CDN** — Cloud CDN or Firebase Hosting for frontend
12. **Set `gcTime: 30min`** on QueryClient
13. **Remove `--no-cache`** from frontend Cloud Build
14. **Add `service.yaml`** to version-control Cloud Run config
15. **Remove `tw-animate-css`**, inline just `animate-pulse`

### Phase 3: Bigger Lifts (week+)

16. **Lazy-import research dependencies** — defer LangChain/LangGraph imports to reduce cold start
17. **Migrate InMemoryResearchStore to Redis** — enable horizontal scaling
18. **Migrate Cloud SQL to us-east1** — same region as backend
19. **Add backend CI/CD pipeline** — `cloudbuild.yaml` with tests
20. **Hardcode or cache President/VP** — eliminate Cicero double-call
