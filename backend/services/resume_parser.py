from __future__ import annotations
"""
Resume parser — supports PDF and DOCX.
Extracts: name, email, phone, skills, experience years,
job titles held, notice period hints, summary/objective.
"""
import re
import io
from pathlib import Path
from datetime import datetime


# ── Helpers ──────────────────────────────────────────────────────────────

def _extract_text_pdf(file_bytes: bytes) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n".join(
                page.extract_text() or "" for page in pdf.pages
            )
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
    else:
        raise ValueError("Unsupported file type: {}. Use PDF or DOCX.".format(ext))


# ── Field extractors ──────────────────────────────────────────────────────

def _extract_email(text: str) -> str:
    m = re.search(r"[\w.+\-]+@[\w\-]+\.[\w.]+", text)
    return m.group(0).lower() if m else ""


def _extract_phone(text: str) -> str:
    m = re.search(r"(?:\+91[\s\-]?)?[6-9]\d{9}|(?:\+\d{1,3}[\s\-]?)?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}", text)
    return m.group(0) if m else ""


def _extract_name(text: str) -> str:
    """Attempt to extract name from first 3 non-empty lines."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines[:5]:
        # Skip lines that look like emails, phones, addresses, or headers
        if re.search(r"@|http|linkedin|github|resume|curriculum|cv|\d{5}", line, re.I):
            continue
        # Likely a name: 2-4 words, mostly capitalized, no special chars
        words = line.split()
        if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
            return line
    return ""


def _extract_skills(text: str) -> list:
    """Extract skills by matching against known skill vocabulary."""
    from backend.services.skill_families import SKILL_FAMILIES
    text_lower = text.lower()
    found = []
    for family_skills in SKILL_FAMILIES.values():
        for skill in family_skills:
            # Word-boundary aware match
            pattern = r"(?<![a-z])" + re.escape(skill) + r"(?![a-z])"
            if re.search(pattern, text_lower):
                found.append(skill)
    # Also look for skills listed after "Skills:" header
    skills_section = re.search(
        r"(?:skills|technical skills|key skills|core competencies)[:\s]+(.{10,500}?)(?:\n\n|\Z)",
        text_lower, re.I | re.DOTALL
    )
    if skills_section:
        raw = skills_section.group(1)
        # split on commas, pipes, bullets, newlines
        items = re.split(r"[,|•\n·▪◦]", raw)
        for item in items:
            item = item.strip().lower()
            if 2 < len(item) < 40:
                found.append(item)
    # Dedupe preserving order
    seen = set()
    result = []
    for s in found:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result


def _extract_experience_years(text: str) -> float:
    """Calculate total years of experience from date ranges in text."""
    # Look for year ranges like 2019-2023, 2019–2022, Jan 2020 - Mar 2023
    year_pattern = re.findall(
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?\s*(\d{4})\s*[-–to]+\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?\s*(\d{4}|present|current|now)",
        text, re.I
    )
    if not year_pattern:
        # Fallback: look for "X years of experience" pattern
        m = re.search(r"(\d+(?:\.\d+)?)\+?\s*years?\s+(?:of\s+)?experience", text, re.I)
        if m:
            return float(m.group(1))
        return 0.0

    total_months = 0
    current_year = datetime.now().year
    for start_yr, end_yr in year_pattern:
        try:
            start = int(start_yr)
            end = current_year if end_yr.lower() in ("present", "current", "now") else int(end_yr)
            if 1990 <= start <= current_year and start <= end:
                total_months += (end - start) * 12
        except ValueError:
            continue

    return round(total_months / 12, 1)


def _extract_job_titles(text: str) -> list:
    """Extract job titles the person has held."""
    KNOWN_TITLES = [
        "data analyst", "senior data analyst", "lead data analyst",
        "business analyst", "senior business analyst",
        "product analyst", "bi analyst", "business intelligence analyst",
        "data scientist", "senior data scientist", "lead data scientist",
        "data engineer", "senior data engineer",
        "analytics engineer", "ml engineer", "machine learning engineer",
        "product manager", "senior product manager", "associate product manager",
        "software engineer", "senior software engineer",
        "full stack developer", "backend developer", "frontend developer",
        "devops engineer", "cloud engineer", "data architect",
        "ux designer", "ui designer", "product designer",
        "project manager", "program manager", "scrum master",
        "marketing analyst", "financial analyst", "operations analyst",
    ]
    text_lower = text.lower()
    found = []
    for title in KNOWN_TITLES:
        if title in text_lower:
            found.append(title)
    return found[:5]  # top 5


def _extract_notice_period(text: str) -> str:
    """Extract notice period if mentioned."""
    m = re.search(
        r"notice\s*period[:\s]+(\d+\s*(?:days?|weeks?|months?)|immediate|serving)",
        text, re.I
    )
    if m:
        return m.group(1).strip()
    m = re.search(r"(\d+)\s*(?:days?|weeks?)\s*notice", text, re.I)
    if m:
        return "{} notice".format(m.group(0))
    return ""


def _extract_summary(text: str) -> str:
    """Extract professional summary / objective section."""
    # Look for a summary section
    m = re.search(
        r"(?:summary|objective|profile|about me)[:\s]*\n(.{50,600}?)(?:\n\n|\n[A-Z]|\Z)",
        text, re.I | re.DOTALL
    )
    if m:
        summary = " ".join(m.group(1).split())
        return summary[:400]
    # Fallback: first substantive paragraph
    paras = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 80]
    if paras:
        return " ".join(paras[0].split())[:400]
    return ""


# ── Main entry point ──────────────────────────────────────────────────────

def parse_resume(file_bytes: bytes, filename: str) -> dict:
    """
    Parse a resume file and return structured profile data.
    All fields default to empty/zero if not found.
    """
    text = extract_text(file_bytes, filename)
    skills = _extract_skills(text)
    titles = _extract_job_titles(text)
    exp = _extract_experience_years(text)

    return {
        "raw_text": text[:8000],   # store first 8k chars
        "name": _extract_name(text),
        "email": _extract_email(text),
        "phone": _extract_phone(text),
        "skills": skills,
        "skills_str": ", ".join(skills),
        "experience_years": exp,
        "job_titles": titles,
        "notice_period": _extract_notice_period(text),
        "summary": _extract_summary(text),
        "word_count": len(text.split()),
    }
