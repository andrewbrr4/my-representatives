import logging
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from routers.representatives import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)

app = FastAPI(title="MyReps API")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    logging.getLogger("myreps.request").info(f"→ {request.method} {request.url.path}")
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    logging.getLogger("myreps.request").info(f"← {request.method} {request.url.path} {response.status_code} ({elapsed:.1f}s)")
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
