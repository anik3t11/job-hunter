from __future__ import annotations
"""
Auth routes — signup, login, me, admin whitelist management.
"""
import os
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from backend.database import (
    get_user_by_email, create_user, is_whitelisted,
    add_to_whitelist, remove_from_whitelist, list_whitelist,
    get_user_by_id, save_settings,
)
from backend.services.auth_service import (
    hash_password, verify_password, create_token,
    get_current_user, get_admin_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── Models ────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email:    str
    password: str
    name:     Optional[str] = ""


class LoginRequest(BaseModel):
    email:    str
    password: str


class WhitelistAdd(BaseModel):
    email: str


# ── Public routes ─────────────────────────────────────────────────────────

@router.post("/signup")
def signup(req: SignupRequest):
    email = req.email.strip().lower()
    if not email or not req.password:
        raise HTTPException(400, "Email and password required")
    if len(req.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    admin_email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    is_admin = bool(admin_email and email == admin_email)

    # Admin email always bypasses whitelist (bootstrap first account)
    if not is_admin and not is_whitelisted(email):
        raise HTTPException(403, "This email is not on the invite list. Ask the admin to add you.")
    if get_user_by_email(email):
        raise HTTPException(409, "An account with this email already exists")
    user_id = create_user(
        email=email,
        password_hash=hash_password(req.password),
        name=req.name or email.split("@")[0],
        is_admin=is_admin,
    )
    token = create_token(user_id, email, is_admin=is_admin)
    return {"ok": True, "token": token, "user": {"id": user_id, "email": email, "name": req.name, "is_admin": is_admin}}


@router.post("/login")
def login(req: LoginRequest):
    email = req.email.strip().lower()
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(401, "Invalid email or password")
    if not user.get("is_active"):
        raise HTTPException(403, "Account is disabled. Contact admin.")
    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")

    token = create_token(user["id"], email, is_admin=bool(user.get("is_admin")))
    return {
        "ok": True,
        "token": token,
        "user": {
            "id":       user["id"],
            "email":    user["email"],
            "name":     user["name"],
            "is_admin": bool(user.get("is_admin")),
        },
    }


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    u = get_user_by_id(user["user_id"])
    if not u:
        raise HTTPException(404, "User not found")
    return {
        "id":       u["id"],
        "email":    u["email"],
        "name":     u["name"],
        "is_admin": bool(u.get("is_admin")),
    }


# ── Admin — whitelist management ──────────────────────────────────────────

@router.get("/admin/whitelist")
def admin_list_whitelist(admin: dict = Depends(get_admin_user)):
    return {"whitelist": list_whitelist()}


@router.post("/admin/whitelist")
def admin_add_whitelist(body: WhitelistAdd, admin: dict = Depends(get_admin_user)):
    email = body.email.strip().lower()
    if not email:
        raise HTTPException(400, "Email required")
    add_to_whitelist(email)
    return {"ok": True, "email": email}


@router.delete("/admin/whitelist/{email}")
def admin_remove_whitelist(email: str, admin: dict = Depends(get_admin_user)):
    remove_from_whitelist(email)
    return {"ok": True}


@router.post("/admin/make-admin/{user_id}")
def make_admin(user_id: int, admin: dict = Depends(get_admin_user)):
    """Promote a user to admin."""
    from backend.database import get_connection
    conn = get_connection()
    conn.execute("UPDATE users SET is_admin=1 WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    return {"ok": True}
