from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from backend.services.auth_service import get_current_user
from backend.database import insert_jobs, get_settings
from backend.services.matcher import score_and_attach
from backend.scrapers.utils import make_url_hash

router = APIRouter(prefix="/api/bookmarklet", tags=["bookmarklet"])


class BookmarkSave(BaseModel):
    title:       str
    url:         str
    company:     Optional[str] = ""
    location:    Optional[str] = ""
    description: Optional[str] = ""


@router.post("/save")
def save_bookmarked_job(body: BookmarkSave, user: dict = Depends(get_current_user)):
    if not body.url:
        return {"ok": False, "error": "URL is required"}

    uid      = user["user_id"]
    settings = get_settings(uid)
    now      = datetime.now(timezone.utc).isoformat()

    job = {
        "title":               body.title[:300] or "Untitled",
        "company":             (body.company or "")[:200],
        "location":            (body.location or "")[:200],
        "salary_min":          None,
        "salary_max":          None,
        "salary_raw":          "",
        "salary_target":       0,
        "experience_required": "",
        "experience_min":      None,
        "experience_max":      None,
        "description":         (body.description or "")[:4000],
        "description_snippet": (body.description or "")[:300],
        "skills_required":     "",
        "job_url":             body.url,
        "url_hash":            make_url_hash(body.url),
        "source":              "bookmarked",
        "country":             settings.get("last_search_country", "IN") or "IN",
        "recruiter_name":      "",
        "recruiter_email":     "",
        "status":              "new",
        "scraped_at":          now,
    }

    job = score_and_attach(job, settings)
    inserted, _ = insert_jobs([job], uid)

    return {
        "ok":      True,
        "saved":   inserted > 0,
        "title":   body.title,
        "company": body.company or "",
    }
