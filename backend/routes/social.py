from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from backend.database import insert_social_posts, get_social_posts, update_social_post, get_settings, get_connection
from backend.scrapers.social import scrape_social
from backend.services.auth_service import get_current_user

router = APIRouter(prefix="/api/social", tags=["social"])


class SocialSearchRequest(BaseModel):
    role:    str
    country: str  = "IN"
    sources: list = ["linkedin_post", "reddit", "hn_hiring"]


class PostUpdate(BaseModel):
    status:       Optional[str] = None
    poster_email: Optional[str] = None


@router.get("/posts")
async def list_posts(
    source:   str = Query(default="all"),
    status:   str = Query(default="all"),
    page:     int = Query(default=1, ge=1),
    per_page: int = Query(default=20, le=50),
    user:     dict = Depends(get_current_user),
):
    posts, total = get_social_posts(
        user_id=user["user_id"], source=source, status=status,
        page=page, per_page=per_page,
    )
    return {"posts": posts, "total": total, "page": page,
            "per_page": per_page, "pages": max(1, -(-total // per_page))}


@router.post("/search")
async def search_social(req: SocialSearchRequest, user: dict = Depends(get_current_user)):
    posts = scrape_social(role=req.role, country=req.country, sources=req.sources)
    if not posts:
        return {"ok": True, "inserted": 0, "skipped": 0, "found": 0}
    inserted, skipped = insert_social_posts(posts, user["user_id"])
    return {"ok": True, "inserted": inserted, "skipped": skipped, "found": len(posts)}


@router.patch("/posts/{post_id}")
async def update_post(post_id: int, body: PostUpdate, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in body.dict().items() if v is not None}
    if updates:
        update_social_post(post_id, user["user_id"], updates)
    return {"ok": True}


@router.post("/posts/{post_id}/email")
async def build_email_for_post(post_id: int, user: dict = Depends(get_current_user)):
    conn = get_connection()
    row  = conn.execute(
        "SELECT * FROM social_posts WHERE id=? AND user_id=?", (post_id, user["user_id"])
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Post not found")

    post     = dict(row)
    settings = get_settings(user["user_id"])
    name     = settings.get("user_name", "")
    exp      = settings.get("user_experience_years", "")
    notice   = settings.get("notice_period", "")
    role     = post.get("role_mentioned") or settings.get("last_search_role", "this role")
    poster   = post.get("poster_name", "")
    company  = post.get("company", "")

    greeting     = "Hi {},".format(poster) if poster else "Hi,"
    company_part = " at {}".format(company) if company else ""
    exp_line     = "I have {} years of experience in this space".format(exp) if exp and exp != "0" \
                   else "I have strong experience in this space"
    notice_line  = " and am available with {} notice period".format(notice) if notice else ""

    subject = "Re: {} Opening{}".format(role.title(), company_part)
    body = (
        "{greeting}\n\n"
        "Saw your post about hiring a {role}{company_part}. "
        "{exp_line}{notice_line}. "
        "Looking forward to hearing from you.\n\n— {name}"
    ).format(
        greeting=greeting, role=role, company_part=company_part,
        exp_line=exp_line, notice_line=notice_line, name=name or "Me",
    )
    return {"to": post.get("poster_email", ""), "subject": subject, "body": body, "post": post}
