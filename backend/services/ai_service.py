from __future__ import annotations
"""
AI service — generates cover letters and tailors resumes per job.

Supports:
  1. Google Gemini (free tier: 1500 req/day — set GEMINI_API_KEY env var)
  2. Groq / Llama-3 (free tier: 14400 req/day — set GROQ_API_KEY env var)

Each user gets AI_DAILY_LIMIT free uses per day (tracked in DB).
Users can override with their own key stored in Settings.
"""
import os
import re
import json
from datetime import datetime, timezone, date

import requests

# Server-level keys (set in Railway env vars)
_SERVER_GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
_SERVER_GROQ_KEY   = os.environ.get("GROQ_API_KEY", "")

AI_DAILY_LIMIT = int(os.environ.get("AI_DAILY_LIMIT", "5"))


# ── Per-user daily quota tracking (simple in-memory + DB fallback) ─────────

_usage: dict[str, int] = {}   # "user_id:YYYY-MM-DD" → count


def _usage_key(user_id: int) -> str:
    today = date.today().isoformat()
    return f"{user_id}:{today}"


def get_remaining(user_id: int, user_key: str = "") -> int:
    """Return how many AI calls this user still has today."""
    if user_key:
        return 999  # own key → unlimited
    used = _usage.get(_usage_key(user_id), 0)
    return max(0, AI_DAILY_LIMIT - used)


def _consume(user_id: int):
    k = _usage_key(user_id)
    _usage[k] = _usage.get(k, 0) + 1


# ── Gemini call ────────────────────────────────────────────────────────────

def _call_gemini(prompt: str, api_key: str) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={api_key}"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024},
    }
    resp = requests.post(url, json=body, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


# ── Groq call ──────────────────────────────────────────────────────────────

def _call_groq(prompt: str, api_key: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
        "temperature": 0.7,
    }
    resp = requests.post(url, json=body, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


# ── Main dispatcher ────────────────────────────────────────────────────────

def _call_ai(prompt: str, user_gemini_key: str = "", user_groq_key: str = "") -> str:
    """Try user key first, then server keys."""
    # 1. User's own Gemini key
    if user_gemini_key:
        return _call_gemini(prompt, user_gemini_key)
    # 2. User's own Groq key
    if user_groq_key:
        return _call_groq(prompt, user_groq_key)
    # 3. Server Gemini key
    if _SERVER_GEMINI_KEY:
        return _call_gemini(prompt, _SERVER_GEMINI_KEY)
    # 4. Server Groq key
    if _SERVER_GROQ_KEY:
        return _call_groq(prompt, _SERVER_GROQ_KEY)
    raise ValueError("No AI API key configured. Add GEMINI_API_KEY or GROQ_API_KEY in settings.")


def _get_user_keys(settings: dict) -> tuple[str, str]:
    """Pull user's own API keys from their settings."""
    return (
        settings.get("gemini_api_key", "") or "",
        settings.get("groq_api_key", "") or "",
    )


# ── Public functions ────────────────────────────────────────────────────────

def generate_cover_letter(job: dict, settings: dict, user_id: int) -> str:
    """Generate a tailored cover letter for a specific job."""
    user_gemini, user_groq = _get_user_keys(settings)
    user_key = user_gemini or user_groq

    if get_remaining(user_id, user_key) <= 0:
        raise ValueError(f"Daily AI limit ({AI_DAILY_LIMIT}) reached. Resets at midnight. Add your own Gemini/Groq key in Settings for unlimited access.")

    name         = settings.get("user_name", "")       or "Job Applicant"
    skills       = settings.get("user_skills", "")     or ""
    exp_years    = settings.get("user_experience_years","0")
    resume_text  = settings.get("resume_summary", "")  or ""
    notice       = settings.get("notice_period", "")   or ""

    job_title    = job.get("title", "")
    company      = job.get("company", "")
    jd_snippet   = (job.get("description") or job.get("description_snippet") or "")[:1500]
    skills_gap   = job.get("skills_gap", "")

    prompt = f"""Write a professional, concise cover letter (3–4 paragraphs, ≤300 words) for this job application.

**Applicant:**
- Name: {name}
- Experience: {exp_years} years
- Key Skills: {skills}
- Notice Period: {notice}
- Background: {resume_text[:500] if resume_text else 'Not provided'}

**Job:**
- Title: {job_title}
- Company: {company}
- Description: {jd_snippet}
- Skills to highlight: {skills_gap if skills_gap else 'Match the JD requirements'}

**Instructions:**
- Open with genuine enthusiasm for THIS company/role (not generic)
- Highlight 2–3 specific achievements/skills that match the JD
- If skills gap exists ({skills_gap}), briefly show willingness to learn
- End with a confident call to action
- Tone: Professional but human, not robotic
- Do NOT use clichés like "I am writing to apply..." or "I am a passionate..."
- Return ONLY the letter text, no subject line, no "Dear Hiring Manager" header needed (user will add)
"""

    result = _call_ai(prompt, user_gemini, user_groq)
    _consume(user_id)
    return result


def tailor_resume_bullets(job: dict, settings: dict, user_id: int) -> str:
    """Return tailored resume bullet points / summary for this specific job."""
    user_gemini, user_groq = _get_user_keys(settings)
    user_key = user_gemini or user_groq

    if get_remaining(user_id, user_key) <= 0:
        raise ValueError(f"Daily AI limit ({AI_DAILY_LIMIT}) reached. Resets at midnight. Add your own Gemini/Groq key in Settings for unlimited access.")

    name        = settings.get("user_name", "")       or "Job Applicant"
    skills      = settings.get("user_skills", "")     or ""
    exp_years   = settings.get("user_experience_years","0")
    resume_text = settings.get("resume_summary", "")  or ""

    job_title   = job.get("title", "")
    company     = job.get("company", "")
    jd_snippet  = (job.get("description") or job.get("description_snippet") or "")[:1500]
    skills_gap  = job.get("skills_gap", "")

    prompt = f"""You are a professional resume writer. Tailor the applicant's resume for this specific job.

**Applicant:**
- Name: {name}
- Experience: {exp_years} years
- Skills: {skills}
- Current Summary/Background: {resume_text[:600] if resume_text else 'Not provided'}

**Target Job:**
- Title: {job_title} at {company}
- Job Description: {jd_snippet}
- Missing skills to address: {skills_gap or 'None identified'}

**Provide:**
1. A tailored professional summary (3–4 sentences, ATS-optimized with keywords from the JD)
2. 4–5 strong resume bullet points that highlight relevant experience for THIS role
   - Use action verbs + quantifiable impact where possible
   - Weave in keywords from the job description naturally

Format as:
## Professional Summary
[summary here]

## Key Achievements / Bullet Points
- [bullet 1]
- [bullet 2]
- [bullet 3]
- [bullet 4]
- [bullet 5]
"""

    result = _call_ai(prompt, user_gemini, user_groq)
    _consume(user_id)
    return result


def get_ai_status(user_id: int, settings: dict) -> dict:
    """Return AI availability and remaining credits for a user."""
    user_gemini, user_groq = _get_user_keys(settings)
    user_key = user_gemini or user_groq
    has_server_key = bool(_SERVER_GEMINI_KEY or _SERVER_GROQ_KEY)
    available = bool(user_key or has_server_key)
    remaining = get_remaining(user_id, user_key)
    return {
        "available":    available,
        "remaining":    remaining,
        "daily_limit":  AI_DAILY_LIMIT,
        "has_own_key":  bool(user_key),
        "provider":     ("gemini" if (user_gemini or _SERVER_GEMINI_KEY) else "groq" if (user_groq or _SERVER_GROQ_KEY) else "none"),
    }
