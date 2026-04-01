import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from routers.representatives import router
from routers.research import router as research_router
from routers.transactions import router as transactions_router
from routers.elections import router as elections_router
from routers.issues import router as issues_router
from db import close_pool
from store.dependencies import get_election_cache, get_issue_cache, get_rep_cache, get_research_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
# Suppress noisy OpenTelemetry context-detach errors from Langfuse's async tracing.
# These occur when asyncio.gather tasks detach context tokens across task boundaries.
# Traces still work correctly — this is cosmetic noise only.
logging.getLogger("opentelemetry.context").setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify Redis connectivity at startup if configured
    if os.getenv("REDIS_URL"):
        try:
            from store.redis import create_redis_client
            client = create_redis_client()
            await client.ping()
            logger.info("Redis connection verified (PING OK)")
            await client.aclose()
        except Exception as e:
            logger.error(f"Redis connection FAILED: {e} — falling back may cause errors")

    async def periodic_cleanup():
        while True:
            await asyncio.sleep(300)  # 5 minutes
            try:
                await get_research_store().cleanup()
                await get_rep_cache().cleanup()
                await get_election_cache().cleanup()
                await get_issue_cache().cleanup()
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    task = asyncio.create_task(periodic_cleanup())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await close_pool()


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="MyReps API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    logging.getLogger("myreps.request").info(f"→ {request.method} {request.url.path}")
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    logging.getLogger("myreps.request").info(
        f"← {request.method} {request.url.path} {response.status_code} ({elapsed:.1f}s)"
    )
    return response

_default_origins = "http://localhost:5173,http://localhost:3000"
allowed_origins = os.getenv("CORS_ORIGINS", _default_origins).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in allowed_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(research_router)
app.include_router(transactions_router)
app.include_router(elections_router)
app.include_router(issues_router)
