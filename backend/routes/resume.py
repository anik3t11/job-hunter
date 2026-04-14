from __future__ import annotations
"""
Resume upload route.
POST /api/resume/upload  — multipart file, returns parsed profile
POST /api/resume/save    — save parsed profile fields to settings
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.services.resume_parser import parse_resume
from backend.database import save_settings, get_settings

router = APIRouter(prefix="/api/resume", tags=["resume"])


@router.post("/upload")
async def upload_resume(file: UploadFile = File(...)):
    """
    Accept a PDF or DOCX resume, parse it, return structured profile.
    Does NOT auto-save — client reviews first, then calls /save.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("pdf", "docx", "doc"):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type '{}'. Please upload PDF or DOCX.".format(ext)
        )

    try:
        content = await file.read()
        if len(content) > 5 * 1024 * 1024:  # 5 MB limit
            raise HTTPException(status_code=400, detail="File too large (max 5 MB)")
        profile = parse_resume(content, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Parse failed: {}".format(e))

    return {"ok": True, "profile": profile}


@router.post("/save")
async def save_resume_profile(data: dict):
    """
    Save extracted resume fields into settings so they pre-fill the profile form.
    Client sends only the fields the user confirmed.
    """
    allowed = {
        "user_name", "user_skills", "user_experience_years",
        "notice_period", "resume_summary", "resume_text",
    }
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to save")

    save_settings(updates)
    return {"ok": True, "saved": list(updates.keys())}


@router.get("/profile")
async def get_resume_profile():
    """Return current resume-related settings for the profile panel."""
    settings = get_settings()
    return {
        "user_name": settings.get("user_name", ""),
        "user_skills": settings.get("user_skills", ""),
        "user_experience_years": settings.get("user_experience_years", "0"),
        "notice_period": settings.get("notice_period", ""),
        "resume_summary": settings.get("resume_summary", ""),
        "has_resume": bool(settings.get("resume_text", "")),
    }
