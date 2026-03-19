"""Manual transaction logging endpoints."""

from fastapi import APIRouter, Query

from db import list_transactions, save_manual_transaction
from models import TransactionCreate, TransactionOut

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.post("/")
async def create_transaction(body: TransactionCreate):
    result = await save_manual_transaction(
        type=body.type,
        source=body.source,
        billing_model=body.billing_model,
        amount_usd=body.amount_usd,
        description=body.description,
        research_task_id=body.research_task_id,
    )
    return result


@router.get("/", response_model=list[TransactionOut])
async def get_transactions(limit: int = Query(default=50, ge=1, le=500)):
    rows = await list_transactions(limit=limit)
    return rows
