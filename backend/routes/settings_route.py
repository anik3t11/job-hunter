from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from backend.database import get_settings, save_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])
SENSITIVE = {"gmail_app_password"}


@router.get("")
def fetch_settings():
    settings = get_settings()
    result = {k: v for k, v in settings.items() if k not in SENSITIVE}
    result["gmail_app_password"] = ""
    return result


class SettingsUpdate(BaseModel):
    gmail_address:            Optional[str] = None
    gmail_app_password:       Optional[str] = None
    user_name:                Optional[str] = None
    user_skills:              Optional[str] = None
    user_experience_years:    Optional[str] = None
    user_preferred_locations: Optional[str] = None
    user_salary_target:       Optional[str] = None
    user_salary_min:          Optional[str] = None   # legacy compat
    resume_summary:           Optional[str] = None
    notice_period:            Optional[str] = None
    resume_text:              Optional[str] = None


@router.post("")
def update_settings(body: SettingsUpdate):
    updates = {}
    for key, value in body.model_dump(exclude_none=True).items():
        if key == "gmail_app_password" and not value:
            continue
        updates[key] = value
    # Keep user_salary_min in sync with user_salary_target
    if "user_salary_target" in updates:
        updates["user_salary_min"] = updates["user_salary_target"]
    if updates:
        save_settings(updates)
    return {"ok": True}
