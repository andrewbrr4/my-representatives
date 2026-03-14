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
from routers.jobs import router as jobs_router
from store.dependencies import get_job_store, get_rep_cache

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async def periodic_cleanup():
        while True:
            await asyncio.sleep(300)  # 5 minutes
            try:
                await get_job_store().cleanup()
                await get_rep_cache().cleanup()
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    task = asyncio.create_task(periodic_cleanup())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


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
    logging.getLogger("myreps.request").info(f"← {request.method} {request.url.path} {response.status_code} ({elapsed:.1f}s)")
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
app.include_router(jobs_router)
