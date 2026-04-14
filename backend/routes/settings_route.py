from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from backend.database import get_settings, save_settings
from backend.services.auth_service import get_current_user

router = APIRouter(prefix="/api/settings", tags=["settings"])
SENSITIVE = {"gmail_app_password"}


@router.get("")
def fetch_settings(user: dict = Depends(get_current_user)):
    settings = get_settings(user["user_id"])
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
    resume_summary:           Optional[str] = None
    notice_period:            Optional[str] = None
    resume_text:              Optional[str] = None


@router.post("")
def update_settings(body: SettingsUpdate, user: dict = Depends(get_current_user)):
    updates = {}
    for key, value in body.model_dump(exclude_none=True).items():
        if key == "gmail_app_password" and not value:
            continue
        updates[key] = value
    if "user_salary_target" in updates:
        updates["user_salary_min"] = updates["user_salary_target"]
    if updates:
        save_settings(user["user_id"], updates)
    return {"ok": True}
