"""Async Postgres connection pool (lazy singleton)."""

import logging
import os
from decimal import Decimal

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


_M = Decimal("1000000")


async def save_transactions(
    *,
    job_id: str,
    input_tokens: int,
    output_tokens: int,
    tool_calls: int,
) -> None:
    """Insert outflow transactions for Anthropic and Tavily costs."""
    pool = await get_pool()

    input_cost_per_m = os.environ.get("ANTHROPIC_INPUT_COST_PER_M")
    output_cost_per_m = os.environ.get("ANTHROPIC_OUTPUT_COST_PER_M")
    tavily_cost_per_search = os.environ.get("TAVILY_COST_PER_SEARCH")

    if input_cost_per_m and output_cost_per_m:
        anthropic_cost = (
            Decimal(input_tokens) * Decimal(input_cost_per_m) / _M
            + Decimal(output_tokens) * Decimal(output_cost_per_m) / _M
        )
        await pool.execute(
            """
            INSERT INTO transactions (type, source, billing_model, amount_usd,
                                      description, job_id)
            VALUES ('outflow', 'anthropic', 'per_request', $1, $2, $3)
            """,
            anthropic_cost,
            f"{input_tokens} input + {output_tokens} output tokens",
            job_id,
        )
    else:
        logger.warning("ANTHROPIC_INPUT_COST_PER_M / ANTHROPIC_OUTPUT_COST_PER_M not set, skipping anthropic transaction")

    if tavily_cost_per_search and tool_calls > 0:
        tavily_cost = Decimal(tool_calls) * Decimal(tavily_cost_per_search)
        await pool.execute(
            """
            INSERT INTO transactions (type, source, billing_model, amount_usd,
                                      description, job_id)
            VALUES ('outflow', 'tavily', 'per_request', $1, $2, $3)
            """,
            tavily_cost,
            f"{tool_calls} web searches",
            job_id,
        )
    elif not tavily_cost_per_search:
        logger.warning("TAVILY_COST_PER_SEARCH not set, skipping tavily transaction")
