from __future__ import annotations
"""
Resume parser v2 — PDF/DOCX → structured profile.
Fixes: experience overlap double-counting, proper summary, resume score + tips.
"""
import re
import io
from pathlib import Path
from datetime import datetime

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

ACTION_VERBS = {
    "led", "built", "developed", "designed", "managed", "created", "delivered",
    "improved", "increased", "reduced", "launched", "implemented", "analyzed",
    "automated", "drove", "achieved", "generated", "grew", "spearheaded",
    "orchestrated", "optimized", "collaborated", "mentored", "owned",
}


# ── Text extraction ───────────────────────────────────────────────────────

def _extract_text_pdf(file_bytes: bytes) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as e:
        raise ValueError("Could not parse PDF: {}".format(e))


def _extract_text_docx(file_bytes: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join(para.text for para in doc.paragraphs)
    except Exception as e:
        raise ValueError("Could not parse DOCX: {}".format(e))


def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return _extract_text_pdf(file_bytes)
    elif ext in (".docx", ".doc"):
        return _extract_text_docx(file_bytes)
    raise ValueError("Unsupported file: {}. Use PDF or DOCX.".format(ext))


# ── Field extractors ──────────────────────────────────────────────────────

def _extract_email(text: str) -> str:
    m = re.search(r"[\w.+\-]+@[\w\-]+\.[\w.]+", text)
    return m.group(0).lower() if m else ""


def _extract_phone(text: str) -> str:
    m = re.search(
        r"(?:\+91[\s\-]?)?[6-9]\d{9}|(?:\+\d{1,3}[\s\-]?)?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}", text
    )
    return m.group(0) if m else ""


def _extract_name(text: str) -> str:
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines[:6]:
        if re.search(r"@|http|linkedin|github|resume|curriculum|cv|\d{5}", line, re.I):
            continue
        words = line.split()
        if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
            return line
    return ""


def _extract_skills(text: str) -> list:
    from backend.services.skill_families import SKILL_FAMILIES
    text_lower = text.lower()
    found = []
    for family_skills in SKILL_FAMILIES.values():
        for skill in family_skills:
            pattern = r"(?<![a-z])" + re.escape(skill) + r"(?![a-z])"
            if re.search(pattern, text_lower):
                found.append(skill)
    # Also parse "Skills:" section
    skills_section = re.search(
        r"(?:skills|technical skills|key skills|core competencies)[:\s]+(.{10,600}?)(?:\n\n|\Z)",
        text_lower, re.I | re.DOTALL,
    )
    if skills_section:
        for item in re.split(r"[,|•\n·▪◦]", skills_section.group(1)):
            item = item.strip().lower()
            if 2 < len(item) < 40:
                found.append(item)
    seen, result = set(), []
    for s in found:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result


def _parse_date(month_str: str, year_str: str) -> tuple:
    """Return (year, month) as ints."""
    year = int(year_str) if year_str.isdigit() else datetime.now().year
    month = MONTH_MAP.get(month_str.lower()[:3], 1) if month_str else 1
    return year, month


def _extract_experience_years(text: str) -> float:
    """
    Calculate total experience with overlap merging so concurrent jobs
    don't get double-counted (fixes the 4yr → 8yr bug).
    """
    current_year  = datetime.now().year
    current_month = datetime.now().month

    # Extract month-year ranges: "Jan 2020 - Mar 2023" or "2019 - 2022"
    full_pattern = re.findall(
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|"
        r"May|June|July|August|September|October|November|December)?\s*(\d{4})\s*"
        r"[-–to/]+\s*"
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|"
        r"May|June|July|August|September|October|November|December|present|current|now|till date|to date)?\s*"
        r"(\d{4})?",
        text, re.I,
    )

    intervals = []
    for start_month, start_year, end_token, end_year in full_pattern:
        try:
            sy, sm = _parse_date(start_month, start_year)
            if not (1990 <= sy <= current_year):
                continue

            if end_token and end_token.lower() in ("present", "current", "now", "till date", "to date"):
                ey, em = current_year, current_month
            elif end_year:
                ey, em = _parse_date(end_token or "", end_year)
            else:
                continue  # can't determine end

            start_abs = sy * 12 + sm
            end_abs   = ey * 12 + em
            if end_abs > start_abs:
                intervals.append((start_abs, end_abs))
        except Exception:
            continue

    if not intervals:
        # Fallback: explicit mention
        m = re.search(r"(\d+(?:\.\d+)?)\+?\s*years?\s+(?:of\s+)?(?:total\s+)?experience", text, re.I)
        if m:
            return float(m.group(1))
        return 0.0

    # Merge overlapping intervals to avoid double-counting
    intervals.sort()
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    total_months = sum(e - s for s, e in merged)
    return round(total_months / 12, 1)


def _extract_job_titles(text: str) -> list:
    KNOWN_TITLES = [
        "data analyst", "senior data analyst", "lead data analyst",
        "business analyst", "senior business analyst",
        "product analyst", "bi analyst", "business intelligence analyst",
        "data scientist", "senior data scientist",
        "data engineer", "senior data engineer",
        "analytics engineer", "ml engineer", "machine learning engineer",
        "product manager", "senior product manager",
        "software engineer", "senior software engineer",
        "full stack developer", "backend developer", "frontend developer",
        "devops engineer", "cloud engineer", "data architect",
        "ux designer", "ui designer", "product designer",
        "project manager", "program manager", "scrum master",
        "marketing analyst", "financial analyst", "operations analyst",
    ]
    text_lower = text.lower()
    return [t for t in KNOWN_TITLES if t in text_lower][:5]


def _extract_notice_period(text: str) -> str:
    m = re.search(
        r"notice\s*period[:\s]+(\d+\s*(?:days?|weeks?|months?)|immediate|serving)",
        text, re.I,
    )
    if m:
        return m.group(1).strip()
    m = re.search(r"(\d+)\s*(?:days?|weeks?)\s*notice", text, re.I)
    if m:
        return m.group(0)
    if re.search(r"\bimmediate\s*(?:joiner|availability|joining)\b", text, re.I):
        return "Immediate"
    return ""


def _build_summary(text: str, name: str, exp_years: float, skills: list, titles: list) -> str:
    """
    Build a clean 2-3 sentence professional summary from resume content.
    Uses template + best extracted achievement sentence — no AI needed.
    """
    # Line 1: Role + experience
    title_str = titles[0].title() if titles else "Professional"
    exp_str = "{} years".format(int(exp_years)) if exp_years >= 1 else "fresher"
    line1 = "{} with {} of experience.".format(title_str, exp_str)

    # Line 2: Top skills
    top_skills = skills[:5] if skills else []
    if top_skills:
        line2 = "Skilled in {}.".format(", ".join(s.title() for s in top_skills))
    else:
        line2 = ""

    # Line 3: Best achievement sentence from resume
    sentences = re.split(r"[.!?]\s+", text)
    best = ""
    best_score = 0
    for sent in sentences:
        words = sent.lower().split()
        score = 0
        # Contains numbers/metrics
        if re.search(r"\d+%|\d+x|\d+\s*(?:lakh|cr|million|k\b|users|clients|projects)", sent, re.I):
            score += 3
        # Contains action verbs
        if any(v in words for v in ACTION_VERBS):
            score += 2
        # Reasonable length
        if 8 <= len(words) <= 30:
            score += 1
        # Not a header/date line
        if re.search(r"\d{4}\s*[-–]\s*(?:\d{4}|present)", sent, re.I):
            score = 0
        if score > best_score:
            best_score = score
            best = sent.strip()

    parts = [line1]
    if line2:
        parts.append(line2)
    if best and best_score >= 3:
        parts.append(best + ".")

    return " ".join(parts)[:500]


# ── Resume scoring ────────────────────────────────────────────────────────

def score_resume(text: str, skills: list, exp_years: float, titles: list, target_role: str = "") -> dict:
    """
    Score resume 0–100 with specific improvement tips.
    Returns {"score": int, "breakdown": dict, "tips": list}
    """
    from backend.services.skill_families import SKILL_FAMILIES
    breakdown = {}
    tips = []
    text_lower = text.lower()
    word_count = len(text.split())

    # ── Contact info (10 pts) ────────────────────────────────────────────
    contact_score = 0
    if re.search(r"[\w.+\-]+@[\w\-]+\.[\w.]+", text):
        contact_score += 4
    if re.search(r"[6-9]\d{9}", text):
        contact_score += 3
    if re.search(r"linkedin\.com", text, re.I):
        contact_score += 3
    else:
        tips.append("Add your LinkedIn profile URL — recruiters check it before calling.")
    breakdown["Contact"] = contact_score

    # ── Length & completeness (10 pts) ──────────────────────────────────
    length_score = 0
    if word_count >= 300:
        length_score += 5
    else:
        tips.append("Resume is too short ({} words). Aim for 400–700 words.".format(word_count))
    if word_count <= 900:
        length_score += 5
    else:
        tips.append("Resume is too long ({} words). Keep it under 900 words — 1 page is ideal.".format(word_count))
    breakdown["Length"] = length_score

    # ── Experience section quality (25 pts) ──────────────────────────────
    exp_score = 0
    # Has dates
    if re.search(r"\d{4}\s*[-–]\s*(?:\d{4}|present|current)", text, re.I):
        exp_score += 8
    else:
        tips.append("Add start/end dates to each job (e.g. Jan 2021 – Mar 2024) so experience is calculated correctly.")
    # Quantified achievements
    metric_hits = len(re.findall(r"\d+\s*%|\d+x|\d+\s*(?:lakh|cr|million|k\b|users|clients)", text, re.I))
    if metric_hits >= 3:
        exp_score += 12
    elif metric_hits >= 1:
        exp_score += 6
        tips.append("Add more metrics — numbers stand out. E.g. 'Improved report speed by 40%' beats 'Improved reports'.")
    else:
        tips.append("No measurable achievements found. Add at least 2-3 numbers (%, time saved, revenue, users).")
    # Experience level alignment
    if exp_years > 0:
        exp_score += 5
    breakdown["Experience"] = exp_score

    # ── Skills section (20 pts) ──────────────────────────────────────────
    skill_score = 0
    if len(skills) >= 8:
        skill_score += 15
    elif len(skills) >= 4:
        skill_score += 10
        tips.append("List more skills. You have {} — aim for 8+.".format(len(skills)))
    else:
        tips.append("Skills section is very thin ({} found). Add a dedicated 'Skills' section with tools you use.".format(len(skills)))
        skill_score += 3
    # Target role keyword match
    if target_role:
        role_words = set(target_role.lower().split())
        skill_names = set(" ".join(skills).lower().split())
        overlap = role_words & skill_names
        if overlap:
            skill_score += 5
    breakdown["Skills"] = skill_score

    # ── Summary/objective (15 pts) ───────────────────────────────────────
    summary_score = 0
    has_summary = re.search(
        r"(?:summary|objective|profile|about me)[:\s]*\n.{40,}", text, re.I | re.DOTALL
    )
    if has_summary:
        summary_score += 15
    else:
        tips.append("Add a 2-3 line professional summary at the top. It's the first thing a recruiter reads.")
    breakdown["Summary"] = summary_score

    # ── Education (10 pts) ───────────────────────────────────────────────
    edu_score = 0
    if re.search(r"b\.?\s*tech|b\.?\s*e\b|m\.?\s*tech|mba|bachelor|master|degree|bsc|msc|b\.?com|graduation", text, re.I):
        edu_score += 10
    else:
        tips.append("Education section not detected. Make sure your degree is clearly mentioned.")
    breakdown["Education"] = edu_score

    # ── Notice period (5 pts) ────────────────────────────────────────────
    notice_score = 0
    if re.search(r"notice|immediate|serving|available", text, re.I):
        notice_score += 5
    else:
        tips.append("Mention your notice period or availability. Recruiters always ask this.")
    breakdown["Notice Period"] = notice_score

    # ── Format signals (5 pts) ───────────────────────────────────────────
    format_score = 0
    if re.search(r"github\.com|portfolio|projects?", text, re.I):
        format_score += 3
    else:
        tips.append("Add a GitHub profile or project portfolio link — especially for tech/data roles.")
    if len(titles) > 0:
        format_score += 2
    breakdown["Format"] = format_score

    total = sum(breakdown.values())

    # Overall tips based on total score
    if total >= 80:
        tips.insert(0, "Great resume! Focus on tailoring it per job using the keyword tips below.")
    elif total >= 60:
        tips.insert(0, "Good foundation. A few improvements can push your call rate significantly higher.")
    else:
        tips.insert(0, "Resume needs work before applying. Fix the issues below to improve your success rate.")

    return {"score": min(total, 100), "breakdown": breakdown, "tips": tips[:8]}


# ── Main entry point ──────────────────────────────────────────────────────

def parse_resume(file_bytes: bytes, filename: str, target_role: str = "") -> dict:
    text   = extract_text(file_bytes, filename)
    skills = _extract_skills(text)
    titles = _extract_job_titles(text)
    exp    = _extract_experience_years(text)
    name   = _extract_name(text)

    summary = _build_summary(text, name, exp, skills, titles)
    scoring = score_resume(text, skills, exp, titles, target_role)

    return {
        "raw_text":        text[:8000],
        "name":            name,
        "email":           _extract_email(text),
        "phone":           _extract_phone(text),
        "skills":          skills,
        "skills_str":      ", ".join(skills),
        "experience_years": exp,
        "job_titles":      titles,
        "notice_period":   _extract_notice_period(text),
        "summary":         summary,
        "word_count":      len(text.split()),
        "score":           scoring["score"],
        "score_breakdown": scoring["breakdown"],
        "tips":            scoring["tips"],
    }
