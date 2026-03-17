"""Async Postgres connection pool (lazy singleton)."""

import logging
import os
from decimal import Decimal

import asyncpg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Return the shared connection pool, creating it on first call.

    Supports two connection modes:
    - DATABASE_URL: standard postgres:// DSN (local dev, direct IP)
    - Cloud SQL Unix socket: set DB_SOCKET_PATH (e.g. /cloudsql/proj:region:inst),
      DB_NAME, DB_USER, DB_PASSWORD
    """
    global _pool
    if _pool is None:
        socket_path = os.environ.get("DB_SOCKET_PATH")
        if socket_path:
            # Cloud Run with Cloud SQL proxy — connect via Unix socket
            db_name = os.environ.get("DB_NAME", "postgres")
            db_user = os.environ.get("DB_USER", "postgres")
            db_password = os.environ.get("DB_PASSWORD", "")
            _pool = await asyncpg.create_pool(
                host=socket_path,
                database=db_name,
                user=db_user,
                password=db_password,
                min_size=1,
                max_size=5,
            )
            logger.info("Postgres pool created via Unix socket: %s", socket_path)
        else:
            dsn = os.environ.get("DATABASE_URL")
            if not dsn:
                raise RuntimeError(
                    "Neither DB_SOCKET_PATH nor DATABASE_URL is set"
                )
            _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
            logger.info("Postgres pool created via DATABASE_URL")
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


async def save_manual_transaction(
    *,
    type: str,
    source: str,
    billing_model: str,
    amount_usd: float,
    description: str | None = None,
    job_id: str | None = None,
) -> dict:
    """Insert a manual transaction and return id + created_at."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO transactions (type, source, billing_model, amount_usd, description, job_id)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, created_at
        """,
        type, source, billing_model, Decimal(str(amount_usd)), description, job_id,
    )
    return {"id": row["id"], "created_at": row["created_at"]}


async def list_transactions(limit: int = 50) -> list[dict]:
    """Return recent transactions ordered by created_at desc."""
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT * FROM transactions ORDER BY created_at DESC LIMIT $1",
        limit,
    )
    return [dict(r) for r in rows]
