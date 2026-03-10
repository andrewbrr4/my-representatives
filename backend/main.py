import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from langfuse import Langfuse
from pydantic_ai import Agent

Langfuse()
Agent.instrument_all()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from routers.representatives import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="MyReps API")
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
