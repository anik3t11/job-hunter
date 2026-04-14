from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta

from backend.database import get_followup_due, get_job_detail, update_job, get_settings
from backend.services.email_sender import send_email

router = APIRouter(prefix="/api/followup", tags=["followup"])

FOLLOWUP_DAYS = 7      # First follow-up: 7 days after applying
FOLLOWUP_2_DAYS = 14   # Second follow-up: 14 days after applying


class SendFollowupRequest(BaseModel):
    job_id: int
    to_email: str
    subject: str
    body: str
    followup_number: int = 1   # 1 or 2


@router.get("")
def list_due_followups():
    """Return all jobs where a follow-up is overdue."""
    return {"followups": get_followup_due()}


@router.post("/send")
def send_followup(req: SendFollowupRequest):
    settings = get_settings()
    gmail_address = settings.get("gmail_address", "")
    gmail_password = settings.get("gmail_app_password", "")

    if not gmail_address or not gmail_password:
        raise HTTPException(
            status_code=400,
            detail="Gmail not configured. Go to Settings.",
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

    now = datetime.now(timezone.utc).isoformat()
    updates = {}

    if req.followup_number == 1:
        updates["followup_1_at"] = now
        # Schedule follow-up 2 in 7 more days
        fu2 = datetime.now(timezone.utc) + timedelta(days=FOLLOWUP_DAYS)
        updates["followup_due_at"] = fu2.isoformat()
    else:
        updates["followup_2_at"] = now
        updates["followup_due_at"] = None   # no more auto follow-ups

    update_job(req.job_id, updates)
    return {"ok": True, "message": message}


@router.post("/{job_id}/dismiss")
def dismiss_followup(job_id: int):
    """Dismiss the follow-up reminder without sending."""
    job = get_job_detail(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    update_job(job_id, {"followup_due_at": None})
    return {"ok": True}


def build_followup_template(job: dict, settings: dict, followup_number: int = 1) -> dict:
    """Build subject + body for a follow-up email."""
    name = settings.get("user_name", "")
    company = job.get("company", "the company")
    title = job.get("title", "the role")
    source = {"linkedin": "LinkedIn", "naukri": "Naukri", "indeed": "Indeed",
              "foundit": "Foundit", "wellfound": "Wellfound"}.get(job.get("source", ""), "a job board")
    applied_at = job.get("applied_at", "")
    applied_date = ""
    if applied_at:
        try:
            dt = datetime.fromisoformat(applied_at.replace("Z", "+00:00"))
            applied_date = dt.strftime("%B %d")
        except Exception:
            applied_date = ""

    subject = "Following up: {} at {} — {}".format(
        title, company,
        "Second follow-up" if followup_number == 2 else "Following up on my application"
    )

    if followup_number == 1:
        body = """Hi,

I wanted to follow up on my application for the {title} position at {company}, which I submitted{date_part}.

I'm very enthusiastic about this opportunity and would love to discuss how my background aligns with your team's needs. Could we schedule a brief call at your convenience?

I'd be happy to provide any additional information you need.

Best regards,
{name}""".format(
            title=title,
            company=company,
            date_part=" on {}".format(applied_date) if applied_date else "",
            name=name or "Applicant",
        )
    else:
        body = """Hi,

I hope you're doing well. I wanted to reach out one more time regarding the {title} role at {company}.

I remain very interested in this opportunity and believe my skills would be a strong fit for your team. If the position is still open, I'd love to connect.

If there's a better time to reconnect or if you need anything from me, please feel free to reach out.

Best regards,
{name}""".format(
            title=title,
            company=company,
            name=name or "Applicant",
        )

    return {"subject": subject, "body": body}
