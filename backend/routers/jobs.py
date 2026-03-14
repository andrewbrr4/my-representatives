from fastapi import APIRouter, HTTPException

from models import JobStatusResponse
from store.dependencies import get_job_store

router = APIRouter()


@router.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str) -> JobStatusResponse:
    job = await get_job_store().get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found or expired.")
    return JobStatusResponse(**job)
