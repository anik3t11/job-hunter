from __future__ import annotations
import json
import re
from datetime import datetime, timezone, timedelta

from backend.services.skill_families import (
    SKILL_FAMILIES, skill_match_score, compute_skills_gap_fuzzy, user_skill_families
)

STOPWORDS = {
    "and", "or", "the", "with", "for", "in", "a", "an", "to", "of",
    "is", "are", "we", "you", "our", "your", "their", "be", "at", "on",
    "as", "by", "from", "that", "this", "have", "will", "can", "must",
    "should", "would", "could", "looking", "seeking", "required", "experience",
}

CITY_ALIASES = {
    "bangalore": ["bengaluru", "blr", "bangalore urban"],
    "bengaluru": ["bangalore", "blr"],
    "mumbai": ["bombay", "mumbai suburban"],
    "delhi": ["new delhi", "ncr", "delhi ncr", "gurugram", "gurgaon", "noida"],
    "hyderabad": ["hyd", "cyberabad", "secunderabad"],
    "chennai": ["madras"],
    "kolkata": ["calcutta"],
    "pune": ["pun", "pimpri"],
    "new york": ["nyc", "new york city", "manhattan"],
    "san francisco": ["sf", "bay area", "silicon valley"],
    "london": ["greater london"],
    "dubai": ["uae"],
}


def _tokenize(text: str) -> set:
    tokens = re.split(r"[^a-zA-Z0-9+#.]", text.lower())
    return {t for t in tokens if t and len(t) > 1 and t not in STOPWORDS}


def _location_matches(job_location: str, preferred: str) -> bool:
    jl = job_location.lower()
    pref = preferred.lower().strip()
    if pref in jl or jl in pref:
        return True
    for alias in CITY_ALIASES.get(pref, []):
        if alias in jl:
            return True
    for canonical, aliases in CITY_ALIASES.items():
        if pref in aliases and canonical in jl:
            return True
    return False


def _compute_role_score(job: dict, role_query: str, user_skills: str) -> tuple:
    """
    Returns (score 0-35, is_stretch bool).
    is_stretch = True if match is via transferable skills, not exact.
    """
    user_tokens = _tokenize("{} {}".format(role_query, user_skills))
    job_text = "{} {} {}".format(
        job.get("title", ""),
        job.get("skills_required", ""),
        job.get("description", "")[:600],
    )
    job_tokens = _tokenize(job_text)

    # Direct token overlap
    exact_overlap = user_tokens & job_tokens
    exact_ratio = len(exact_overlap) / max(len(user_tokens), 1)
    role_score = min(35, int(exact_ratio * 35))

    # Bonus: role name in job title
    if role_query and role_query.lower() in job.get("title", "").lower():
        role_score = min(35, role_score + 12)

    is_stretch = False

    # Fuzzy family transfer boost — if exact is low, check family overlap
    if role_score < 20 and user_skills:
        user_families = user_skill_families(user_skills)
        jd_full = job_text.lower()
        family_hits = 0
        for family_name, family_skills in SKILL_FAMILIES.items():
            if family_name in user_families:
                for skill in family_skills:
                    if skill in jd_full:
                        family_hits += 1
                        break
        if family_hits > 0:
            transfer_boost = min(15, family_hits * 5)
            if transfer_boost > 0:
                role_score = min(35, role_score + transfer_boost)
                is_stretch = True  # match came from transferable skills

    return max(0, role_score), is_stretch


def score(job: dict, settings: dict) -> tuple:
    breakdown = {}

    role_query = settings.get("last_search_role", "")
    user_skills = settings.get("user_skills", "")

    # ── Role match (0–35) + stretch detection ──
    role_score, is_stretch = _compute_role_score(job, role_query, user_skills)
    breakdown["role"] = role_score

    # ── Location match (0–25) ──
    preferred_raw = settings.get("user_preferred_locations", "")
    search_locations = settings.get("last_search_locations", "")
    all_preferred = [
        p.strip() for p in (preferred_raw + "," + search_locations).split(",") if p.strip()
    ]
    job_location = job.get("location", "").lower()

    if "remote" in job_location or "anywhere" in job_location:
        location_score = 25
    elif all_preferred:
        location_score = 0
        for pref in all_preferred:
            if _location_matches(job_location, pref):
                location_score = 25
                break
    else:
        location_score = 12
    breakdown["location"] = location_score

    # ── Salary match (0–20) ±30% flex ──
    try:
        user_target = int(settings.get("user_salary_target", 0) or 0)
    except (ValueError, TypeError):
        user_target = 0

    job_sal_min = job.get("salary_min")
    job_sal_max = job.get("salary_max")

    if job_sal_min is None or user_target == 0:
        salary_score = 10
    else:
        flex_lo = user_target * 0.70
        job_mid = ((job_sal_min or 0) + (job_sal_max or job_sal_min or 0)) / 2
        if job_mid >= flex_lo:
            salary_score = 20
        else:
            gap_ratio = job_mid / max(flex_lo, 1)
            salary_score = max(0, int(gap_ratio * 20))
    breakdown["salary"] = salary_score

    # ── Experience match (0–20) ──
    try:
        user_exp = float(settings.get("user_experience_years", 0) or 0)
    except (ValueError, TypeError):
        user_exp = 0

    exp_min = job.get("experience_min")
    exp_max = job.get("experience_max")

    if exp_min is None:
        exp_score = 10
    elif exp_min <= user_exp <= (exp_max if exp_max is not None else 99):
        exp_score = 20
    elif user_exp < exp_min:
        gap = exp_min - user_exp
        exp_score = max(0, 20 - int(gap * 5))
    else:
        gap = user_exp - (exp_max or 0)
        exp_score = max(10, 20 - int(gap * 2))
    breakdown["experience"] = exp_score

    total = max(0, min(100, role_score + location_score + salary_score + exp_score))
    return total, breakdown, is_stretch


def is_hot(scraped_at: str) -> bool:
    try:
        dt = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt) < timedelta(days=3)
    except Exception:
        return False


def score_and_attach(job: dict, settings: dict) -> dict:
    total, breakdown, is_stretch = score(job, settings)
    job["match_score"] = total
    job["match_breakdown"] = json.dumps(breakdown)
    job["is_hot"] = 1 if is_hot(job.get("scraped_at", "")) else 0
    job["is_stretch"] = 1 if is_stretch else 0

    # Fuzzy gap: exact missing skills + transferable stretch skills
    user_skills = settings.get("user_skills", "")
    gap_exact, gap_stretch = compute_skills_gap_fuzzy(job, user_skills)
    job["skills_gap"]     = ", ".join(gap_exact)    # must learn
    job["skills_stretch"] = ", ".join(gap_stretch)  # can transfer
    return job
