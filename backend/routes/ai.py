from __future__ import annotations
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from backend.database import get_job_detail, get_settings
from backend.services.ai_service import (
    generate_cover_letter, tailor_resume_bullets, get_ai_status
)
from backend.services.auth_service import get_current_user

router = APIRouter(prefix="/api/ai", tags=["ai"])


class AIJobRequest(BaseModel):
    job_id: int


@router.get("/status")
def ai_status(user: dict = Depends(get_current_user)):
    settings = get_settings(user["user_id"])
    return get_ai_status(user["user_id"], settings)


@router.post("/cover-letter")
def cover_letter(req: AIJobRequest, user: dict = Depends(get_current_user)):
    uid = user["user_id"]
    job = get_job_detail(req.job_id, uid)
    if not job:
        raise HTTPException(404, "Job not found")
    settings = get_settings(uid)
    try:
        text = generate_cover_letter(job, settings, uid)
    except ValueError as e:
        raise HTTPException(429, str(e))
    except Exception as e:
        raise HTTPException(500, f"AI error: {e}")
    return {"text": text, "job_title": job.get("title"), "company": job.get("company")}


@router.post("/tailor-resume")
def tailor_resume(req: AIJobRequest, user: dict = Depends(get_current_user)):
    uid = user["user_id"]
    job = get_job_detail(req.job_id, uid)
    if not job:
        raise HTTPException(404, "Job not found")
    settings = get_settings(uid)
    try:
        text = tailor_resume_bullets(job, settings, uid)
    except ValueError as e:
        raise HTTPException(429, str(e))
    except Exception as e:
        raise HTTPException(500, f"AI error: {e}")
    return {"text": text, "job_title": job.get("title"), "company": job.get("company")}
