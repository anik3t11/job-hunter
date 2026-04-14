from __future__ import annotations
"""
Social hiring posts routes.
GET  /api/social/posts            — list posts with filters
POST /api/social/search           — trigger a fresh scrape
PATCH /api/social/posts/{id}      — update status
POST /api/social/posts/{id}/email — build cold email template for a post
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from backend.database import (
    insert_social_posts, get_social_posts, update_social_post, get_settings
)
from backend.scrapers.social import scrape_social

router = APIRouter(prefix="/api/social", tags=["social"])


class SocialSearchRequest(BaseModel):
    role: str
    country: str = "IN"
    sources: list = ["linkedin_post", "reddit", "twitter"]


class PostUpdate(BaseModel):
    status: Optional[str] = None
    poster_email: Optional[str] = None


@router.get("/posts")
async def list_posts(
    country: str = "all",
    source: str = "all",
    status: str = "all",
    page: int = 1,
    per_page: int = 20,
):
    posts, total = get_social_posts(
        country=country, source=source, status=status, page=page, per_page=per_page
    )
    return {
        "posts": posts,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, -(-total // per_page)),
    }


@router.post("/search")
async def search_social(req: SocialSearchRequest):
    posts = scrape_social(role=req.role, country=req.country, sources=req.sources)
    if not posts:
        return {"ok": True, "inserted": 0, "skipped": 0, "found": 0}
    inserted, skipped = insert_social_posts(posts)
    return {"ok": True, "inserted": inserted, "skipped": skipped, "found": len(posts)}


@router.patch("/posts/{post_id}")
async def update_post(post_id: int, body: PostUpdate):
    updates = {k: v for k, v in body.dict().items() if v is not None}
    if updates:
        update_social_post(post_id, updates)
    return {"ok": True}


@router.post("/posts/{post_id}/email")
async def build_email_for_post(post_id: int):
    """Build a personalised cold email template for a social hiring post."""
    from backend.database import get_connection
    conn = get_connection()
    row = conn.execute("SELECT * FROM social_posts WHERE id = ?", (post_id,)).fetchone()
    conn.close()

    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Post not found")

    post = dict(row)
    settings = get_settings()

    user_name = settings.get("user_name", "")
    user_exp = settings.get("user_experience_years", "")
    notice = settings.get("notice_period", "")
    role = post.get("role_mentioned") or settings.get("last_search_role", "this role")
    poster_name = post.get("poster_name", "")
    company = post.get("company", "")

    greeting = "Hi {},".format(poster_name) if poster_name else "Hi,"
    company_line = " at {}".format(company) if company else ""

    exp_line = ""
    if user_exp and user_exp != "0":
        exp_line = "I have {} years of experience in this space".format(user_exp)
    else:
        exp_line = "I have strong experience in this space"

    notice_line = ""
    if notice:
        notice_line = " and am available with {} notice period".format(notice)

    subject = "Re: {} Opening{}".format(role.title(), company_line)
    body = (
        "{greeting}\n\n"
        "Saw your post about hiring a {role}{company_line}. "
        "{exp_line}{notice_line}. "
        "Looking forward to hearing from you.\n\n"
        "— {name}"
    ).format(
        greeting=greeting,
        role=role,
        company_line=company_line,
        exp_line=exp_line,
        notice_line=notice_line,
        name=user_name or "Me",
    )

    return {
        "to": post.get("poster_email", ""),
        "subject": subject,
        "body": body,
        "post": post,
    }
