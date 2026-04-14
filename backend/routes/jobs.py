from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
import json
from datetime import datetime, timezone, timedelta

from backend.database import get_jobs, get_job_detail, update_job, get_stats, clear_jobs, export_jobs_csv

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

FOLLOWUP_DAYS = 7


class StatusUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
def list_jobs(
    status: str = Query(default="all"),
    source: str = Query(default="all"),
    country: str = Query(default="all"),
    min_score: Optional[int] = Query(default=None),
    followup_due: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, le=100),
    sort: str = Query(default="score"),
):
    jobs, total = get_jobs(
        status=status if status != "all" else None,
        source=source if source != "all" else None,
        country=country if country != "all" else None,
        min_score=min_score,
        followup_due=followup_due,
        page=page,
        per_page=per_page,
        sort=sort,
    )
    for job in jobs:
        try:
            job["match_breakdown"] = json.loads(job.get("match_breakdown") or "{}")
        except Exception:
            job["match_breakdown"] = {}
    return {"jobs": jobs, "total": total, "page": page, "per_page": per_page}


@router.get("/stats")
def job_stats():
    return get_stats()


@router.get("/export/csv")
def export_csv():
    csv_data = export_jobs_csv()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=jobs.csv"},
    )


@router.get("/{job_id}")
def job_detail(job_id: int):
    job = get_job_detail(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        job["match_breakdown"] = json.loads(job.get("match_breakdown") or "{}")
    except Exception:
        job["match_breakdown"] = {}
    return job


@router.patch("/{job_id}")
def patch_job(job_id: int, body: StatusUpdate):
    job = get_job_detail(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    updates = {}
    if body.status is not None:
        valid = {"new", "reviewed", "applied", "interview"}
        if body.status not in valid:
            raise HTTPException(status_code=400, detail="Invalid status")
        updates["status"] = body.status
        if body.status == "applied" and not job.get("applied_at"):
            now = datetime.now(timezone.utc)
            updates["applied_at"] = now.isoformat()
            # Schedule first follow-up
            updates["followup_due_at"] = (now + timedelta(days=FOLLOWUP_DAYS)).isoformat()
    if body.notes is not None:
        updates["notes"] = body.notes

    if updates:
        update_job(job_id, updates)
    return {"ok": True}


@router.delete("/clear/all")
def delete_all_jobs():
    clear_jobs()
    return {"ok": True}
