from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from backend.services.resume_parser import parse_resume
from backend.database import save_settings, get_settings
from backend.services.auth_service import get_current_user

router = APIRouter(prefix="/api/resume", tags=["resume"])


@router.post("/upload")
async def upload_resume(
    file:        UploadFile = File(...),
    target_role: str        = "",
    user:        dict       = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(400, "No file provided")
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("pdf", "docx", "doc"):
        raise HTTPException(400, "Unsupported file type. Upload PDF or DOCX.")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 5 MB)")
    if not target_role:
        settings    = get_settings(user["user_id"])
        target_role = settings.get("last_search_role", "")
    try:
        profile = parse_resume(content, file.filename, target_role)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, "Parse failed: {}".format(e))
    score_data = {
        "score":     profile.get("score", 0),
        "breakdown": profile.get("score_breakdown", {}),
        "tips":      profile.get("tips", []),
    }
    return {"ok": True, "profile": profile, "score": score_data}


@router.post("/save")
async def save_resume_profile(data: dict, user: dict = Depends(get_current_user)):
    allowed = {
        "user_name", "user_skills", "user_experience_years",
        "notice_period", "resume_summary", "resume_text",
    }
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        raise HTTPException(400, "No valid fields to save")
    save_settings(user["user_id"], updates)
    return {"ok": True, "saved": list(updates.keys())}


@router.get("/profile")
async def get_profile(user: dict = Depends(get_current_user)):
    s = get_settings(user["user_id"])
    return {
        "user_name":            s.get("user_name", ""),
        "user_skills":          s.get("user_skills", ""),
        "user_experience_years": s.get("user_experience_years", "0"),
        "notice_period":        s.get("notice_period", ""),
        "resume_summary":       s.get("resume_summary", ""),
        "has_resume":           bool(s.get("resume_text", "")),
    }
