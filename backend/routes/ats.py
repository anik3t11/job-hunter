from __future__ import annotations
import re
from fastapi import APIRouter, Depends
from backend.services.auth_service import get_current_user
from backend.database import get_job_detail, get_settings

router = APIRouter(prefix="/api/ats", tags=["ats"])

STOPWORDS = {
    "and","or","the","with","for","in","a","an","to","of","is","are","we","you","our",
    "your","their","be","at","on","as","by","from","that","this","have","will","can",
    "must","should","would","could","looking","seeking","required","experience","work",
    "working","strong","good","excellent","ability","skills","knowledge","understanding",
    "team","company","role","position","opportunity","years","year","job","using","use",
    "used","across","within","including","etc","like","well","also","about","its","has",
    "been","not","but","if","do","all","any","more","other","such","than","into","over",
    "after","where","when","while","who","which","what","how","they","their","them",
    "these","those","both","each","few","most","some","then","too","very","are","was",
    "were","had","did","get","got","make","made","take","need","new","may","one","two",
    "per","day","week","month","plus","base","level","senior","junior","lead","mid",
    "full","time","part","remote","hybrid","office","minimum","maximum","least","highly",
}

def _extract_keywords(text: str) -> set[str]:
    text = text.lower()
    tokens = re.split(r"[^a-z0-9#+.]", text)
    return {
        t for t in tokens
        if len(t) >= 3 and t not in STOPWORDS and not t.isdigit()
    }


@router.get("/match/{job_id}")
def ats_match(job_id: int, user: dict = Depends(get_current_user)):
    uid = user["user_id"]
    job = get_job_detail(job_id, uid)
    if not job:
        return {"error": "Job not found."}

    s = get_settings(uid)
    resume_text = (s.get("resume_text") or s.get("resume_summary") or "").strip()
    if not resume_text:
        return {"error": "No resume found. Upload your resume in the Resume tab first."}

    jd_text = " ".join(filter(None, [
        job.get("title", ""),
        job.get("description", ""),
        job.get("skills_required", ""),
    ]))

    jd_kw     = _extract_keywords(jd_text)
    resume_kw = _extract_keywords(resume_text)

    # Also check user_skills field
    skills_kw = _extract_keywords(s.get("user_skills", "") or "")
    resume_kw |= skills_kw

    matched = sorted(jd_kw & resume_kw)
    missing = sorted(jd_kw - resume_kw)
    score   = round(len(matched) / max(len(jd_kw), 1) * 100)

    return {
        "score":             score,
        "matched":           matched,
        "missing":           missing,
        "total_jd_keywords": len(jd_kw),
    }
