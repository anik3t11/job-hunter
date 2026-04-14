from __future__ import annotations
from fastapi import APIRouter, Depends
from backend.database import get_analytics
from backend.services.auth_service import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("")
def analytics(user: dict = Depends(get_current_user)):
    return get_analytics(user["user_id"])
