from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta

from backend.database import get_followup_due, get_job_detail, update_job, get_settings
from backend.services.email_sender import send_email
from backend.services.auth_service import get_current_user

router = APIRouter(prefix="/api/followup", tags=["followup"])
FOLLOWUP_DAYS = 7


class SendFollowupRequest(BaseModel):
    job_id:          int
    to_email:        str
    subject:         str
    body:            str
    followup_number: int = 1


@router.get("")
def list_due(user: dict = Depends(get_current_user)):
    return {"followups": get_followup_due(user["user_id"])}


@router.post("/send")
def send_followup(req: SendFollowupRequest, user: dict = Depends(get_current_user)):
    uid      = user["user_id"]
    settings = get_settings(uid)
    gmail    = settings.get("gmail_address", "")
    pwd      = settings.get("gmail_app_password", "")
    if not gmail or not pwd:
        raise HTTPException(400, "Gmail not configured. Go to Settings.")

    ok, msg = send_email(gmail, pwd, req.to_email, req.subject, req.body)
    if not ok:
        raise HTTPException(500, msg)

    now = datetime.now(timezone.utc).isoformat()
    updates = {}
    if req.followup_number == 1:
        updates["followup_1_at"]   = now
        updates["followup_due_at"] = (datetime.now(timezone.utc) + timedelta(days=FOLLOWUP_DAYS)).isoformat()
    else:
        updates["followup_2_at"]   = now
        updates["followup_due_at"] = None
    update_job(req.job_id, uid, updates)
    return {"ok": True, "message": msg}


@router.post("/{job_id}/dismiss")
def dismiss(job_id: int, user: dict = Depends(get_current_user)):
    job = get_job_detail(job_id, user["user_id"])
    if not job:
        raise HTTPException(404, "Job not found")
    update_job(job_id, user["user_id"], {"followup_due_at": None})
    return {"ok": True}
