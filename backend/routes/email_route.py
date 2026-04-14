from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta

from backend.database import get_settings, get_job_detail, update_job
from backend.services.email_sender import send_email, test_connection
from backend.services.auth_service import get_current_user

router = APIRouter(prefix="/api/email", tags=["email"])
FOLLOWUP_DAYS = 7


class SendEmailRequest(BaseModel):
    to_email: str
    subject:  str
    body:     str
    job_id:   Optional[int] = None


@router.post("/send")
def send_cold_email(req: SendEmailRequest, user: dict = Depends(get_current_user)):
    uid      = user["user_id"]
    settings = get_settings(uid)
    gmail    = settings.get("gmail_address", "")
    pwd      = settings.get("gmail_app_password", "")

    if not gmail or not pwd:
        raise HTTPException(400, "Gmail not configured. Go to Settings.")

    ok, msg = send_email(gmail, pwd, req.to_email, req.subject, req.body)
    if not ok:
        raise HTTPException(500, msg)

    # Mark job applied + schedule follow-up
    if req.job_id:
        job = get_job_detail(req.job_id, uid)
        if job and job.get("status") != "applied":
            now = datetime.now(timezone.utc)
            update_job(req.job_id, uid, {
                "status":          "applied",
                "applied_at":      now.isoformat(),
                "followup_due_at": (now + timedelta(days=FOLLOWUP_DAYS)).isoformat(),
            })

    return {"ok": True, "message": msg}


@router.post("/test")
def test_email_connection(user: dict = Depends(get_current_user)):
    settings = get_settings(user["user_id"])
    ok, msg  = test_connection(
        settings.get("gmail_address", ""),
        settings.get("gmail_app_password", ""),
    )
    return {"ok": ok, "message": msg}
