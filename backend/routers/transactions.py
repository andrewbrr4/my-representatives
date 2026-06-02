"""Manual transaction logging endpoints.

Admin-only: the transactions ledger holds internal cost/financial data, so both
routes are gated behind an `ADMIN_API_KEY` (sent as the `X-Admin-Key` header) and
fail closed — if the env var is unset, every request is rejected. The frontend
never calls these; only `admin.ipynb` does (pass the key via the header).
"""

import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from db import list_transactions, save_manual_transaction
from models import TransactionCreate, TransactionOut

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def require_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    """Fail-closed admin gate: rejects unless X-Admin-Key matches ADMIN_API_KEY."""
    expected = os.getenv("ADMIN_API_KEY")
    if not expected or not x_admin_key or not hmac.compare_digest(x_admin_key, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/", dependencies=[Depends(require_admin_key)])
@limiter.limit("10/minute")
async def create_transaction(request: Request, body: TransactionCreate):
    result = await save_manual_transaction(
        type=body.type,
        source=body.source,
        billing_model=body.billing_model,
        amount_usd=body.amount_usd,
        description=body.description,
        research_task_id=body.research_task_id,
    )
    return result


@router.get("/", response_model=list[TransactionOut], dependencies=[Depends(require_admin_key)])
@limiter.limit("10/minute")
async def get_transactions(request: Request, limit: int = Query(default=50, ge=1, le=500)):
    rows = await list_transactions(limit=limit)
    return rows
