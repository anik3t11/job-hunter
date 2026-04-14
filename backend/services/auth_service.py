from __future__ import annotations
"""
Auth service — JWT tokens + PBKDF2 password hashing (no C-extension deps).
"""
import hashlib
import hmac
import os
import secrets
import jwt
from datetime import datetime, timedelta, timezone

SECRET_KEY = os.environ.get("JWT_SECRET", "jh-secret-change-in-prod-" + "x" * 32)
ALGORITHM  = "HS256"
TOKEN_DAYS = 30


# ── Password hashing (PBKDF2 — built-in Python, no bcrypt needed) ──────────

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return "{}:{}".format(salt, dk.hex())


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, dk_hex = stored.split(":", 1)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


# ── JWT ────────────────────────────────────────────────────────────────────

def create_token(user_id: int, email: str, is_admin: bool = False) -> str:
    payload = {
        "user_id":  user_id,
        "email":    email,
        "is_admin": is_admin,
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ── FastAPI dependency ─────────────────────────────────────────────────────

from fastapi import Depends, HTTPException, Header

def get_current_user(authorization: str = Header(default="")) -> dict:
    """Extract and validate Bearer JWT from Authorization header."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization[7:]
    try:
        return decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired — please log in again")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_admin_user(user: dict = Depends(get_current_user)) -> dict:
    """Require admin role."""
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
