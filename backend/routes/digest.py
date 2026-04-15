from __future__ import annotations
from fastapi import APIRouter, Depends
from backend.services.auth_service import get_current_user
from backend.services.digest import send_digest_for_user, get_new_jobs_since
from backend.database import get_settings

router = APIRouter(prefix="/api/digest", tags=["digest"])


@router.post("/send-now")
def send_digest_now(user: dict = Depends(get_current_user)):
    result = send_digest_for_user(user["user_id"])
    return result


@router.get("/preview")
def preview_digest(user: dict = Depends(get_current_user)):
    uid = user["user_id"]
    s   = get_settings(uid)
    min_score = int(s.get("alert_min_score", 50) or 50)
    freq      = s.get("alert_frequency", "daily")
    hours     = 168 if freq == "weekly" else 24
    jobs = get_new_jobs_since(uid, hours=hours, min_score=min_score)
    return {"jobs": jobs, "jobs_count": len(jobs), "hours_window": hours, "min_score": min_score}
