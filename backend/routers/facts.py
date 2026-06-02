from fastapi import APIRouter
from pydantic import BaseModel

from db import get_civics_facts

router = APIRouter()


class FactsResponse(BaseModel):
    facts: list[str]


@router.get("/api/facts")
async def get_facts(issue: str | None = None) -> FactsResponse:
    return FactsResponse(facts=await get_civics_facts(issue))
