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


async def save_research_task(
    *,
    research_id: str,
    representative: str,
    input_tokens: int,
    output_tokens: int,
    tool_calls: int,
    status: str,
    model: str | None = None,
    input_cost_per_m: Decimal | None = None,
    output_cost_per_m: Decimal | None = None,
    search_tool: str | None = None,
    cost_per_search: Decimal | None = None,
    environment: str | None = None,
) -> None:
    """Insert a row into the research_tasks table."""
    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO research_tasks (id, representative, input_tokens, output_tokens,
                          tool_calls, status, model, input_cost_per_m,
                          output_cost_per_m, search_tool, cost_per_search, environment)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """,
        research_id, representative, input_tokens, output_tokens,
        tool_calls, status, model, input_cost_per_m,
        output_cost_per_m, search_tool, cost_per_search, environment,
    )


_M = Decimal("1000000")


async def save_transactions(
    *,
    research_task_id: str,
    model: str | None,
    input_tokens: int,
    output_tokens: int,
    input_cost_per_m: Decimal | None,
    output_cost_per_m: Decimal | None,
    search_tool: str | None,
    tool_calls: int,
    cost_per_search: Decimal | None,
) -> None:
    """Insert outflow transactions for LLM and search costs."""
    pool = await get_pool()

    if input_cost_per_m and output_cost_per_m:
        llm_cost = (
            Decimal(input_tokens) * input_cost_per_m / _M
            + Decimal(output_tokens) * output_cost_per_m / _M
        )
        source = model or "anthropic"
        await pool.execute(
            """
            INSERT INTO transactions (type, source, billing_model, amount_usd,
                                      description, research_task_id)
            VALUES ('outflow', $1, 'per_request', $2, $3, $4)
            """,
            source,
            llm_cost,
            f"{input_tokens} input + {output_tokens} output tokens",
            research_task_id,
        )
    else:
        logger.warning(
            "Input/output cost per M not provided, skipping LLM transaction"
        )

    if cost_per_search and tool_calls > 0:
        total_search_cost = Decimal(tool_calls) * cost_per_search
        source = search_tool or "search"
        await pool.execute(
            """
            INSERT INTO transactions (type, source, billing_model, amount_usd,
                                      description, research_task_id)
            VALUES ('outflow', $1, 'per_request', $2, $3, $4)
            """,
            source,
            total_search_cost,
            f"{tool_calls} web searches",
            research_task_id,
        )
    elif not cost_per_search:
        logger.warning("Cost per search not provided, skipping search transaction")


async def save_manual_transaction(
    *,
    type: str,
    source: str,
    billing_model: str,
    amount_usd: float,
    description: str | None = None,
    research_task_id: str | None = None,
) -> dict:
    """Insert a manual transaction and return id + created_at."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO transactions (type, source, billing_model, amount_usd, description, research_task_id)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, created_at
        """,
        type, source, billing_model, Decimal(str(amount_usd)), description, research_task_id,
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
