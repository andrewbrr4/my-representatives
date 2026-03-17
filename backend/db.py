"""Async Postgres connection pool (lazy singleton)."""

import logging
import os

import asyncpg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Return the shared connection pool, creating it on first call."""
    global _pool
    if _pool is None:
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            raise RuntimeError("DATABASE_URL environment variable is not set")
        _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
        logger.info("Postgres connection pool created")
    return _pool


async def close_pool() -> None:
    """Shut down the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Postgres connection pool closed")


async def save_job(
    *,
    job_id: str,
    address: str,
    reps_found: int,
    reps_researched: int,
    reps_cached: int,
    input_tokens: int,
    output_tokens: int,
    tool_calls: int,
    status: str,
) -> None:
    """Insert a row into the jobs table."""
    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO jobs (id, address, reps_found, reps_researched, reps_cached,
                          input_tokens, output_tokens, tool_calls, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """,
        job_id, address, reps_found, reps_researched, reps_cached,
        input_tokens, output_tokens, tool_calls, status,
    )
