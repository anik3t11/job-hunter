from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone

from backend.database import get_settings, get_job_detail, update_job
from backend.services.email_sender import send_email, test_connection

router = APIRouter(prefix="/api/email", tags=["email"])


class SendEmailRequest(BaseModel):
    job_id: int
    to_email: str
    subject: str
    body: str


@router.post("/send")
def send_cold_email(req: SendEmailRequest):
    settings = get_settings()
    gmail_address = settings.get("gmail_address", "")
    gmail_password = settings.get("gmail_app_password", "")

    if not gmail_address or not gmail_password:
        raise HTTPException(
            status_code=400,
            detail="Gmail not configured. Go to Settings and add your Gmail address and App Password.",
        )

    success, message = send_email(
        gmail_address=gmail_address,
        gmail_app_password=gmail_password,
        to_email=req.to_email,
        subject=req.subject,
        body=req.body,
    )

    if not success:
        raise HTTPException(status_code=500, detail=message)

    # Mark job as applied
    job = get_job_detail(req.job_id)
    if job and job.get("status") != "applied":
        update_job(
            req.job_id,
            {
                "status": "applied",
                "applied_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    return {"ok": True, "message": message}


@router.post("/test")
def test_email_connection():
    settings = get_settings()
    gmail_address = settings.get("gmail_address", "")
    gmail_password = settings.get("gmail_app_password", "")

    ok, message = test_connection(gmail_address, gmail_password)
    return {"ok": ok, "message": message}
