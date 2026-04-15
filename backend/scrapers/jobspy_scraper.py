from __future__ import annotations
"""
JobSpy-powered scraper — wraps the python-jobspy library.
Covers: LinkedIn, Indeed, Glassdoor, Google Jobs concurrently.
Requires Python ≥ 3.10 and python-jobspy ≥ 1.1.80 (see requirements.txt).
Falls back gracefully if the library is unavailable.
"""
import sys
import re
from datetime import datetime, timezone

from .base import BaseScraper
from .utils import make_url_hash, extract_emails, parse_experience

# JobSpy country codes for Indeed
INDEED_COUNTRY_MAP = {
    "IN": "India",
    "US": "USA",
    "GB": "UK",
    "CA": "Canada",
    "AU": "Australia",
    "SG": "Singapore",
    "AE": "UAE",
    "DE": "Germany",
    "NL": "Netherlands",
    "FR": "France",
}

# Map jobspy site names → our source names
SITE_SOURCE_MAP = {
    "linkedin":      "linkedin",
    "indeed":        "indeed",
    "glassdoor":     "glassdoor",
    "google":        "google_jobs",
    "zip_recruiter": "ziprecruiter",
}


def _to_annual_inr(amount, interval: str, currency: str) -> int | None:
    """Convert any salary amount to approximate annual INR."""
    if amount is None:
        return None
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return None

    # Normalise to annual
    interval = (interval or "").upper()
    if interval == "HOURLY":
        amount = amount * 8 * 250        # ~250 working days
    elif interval == "DAILY":
        amount = amount * 250
    elif interval == "WEEKLY":
        amount = amount * 52
    elif interval == "MONTHLY":
        amount = amount * 12
    # else YEARLY — use as-is

    # Convert to INR
    currency = (currency or "").upper()
    if currency in ("INR", "₹", "RS", ""):
        # Some Indian sites report in lakhs (< 500 means lakhs notation)
        if amount < 500:
            amount = amount * 100_000
        return int(amount)
    elif currency in ("USD", "$"):
        return int(amount * 83)
    elif currency in ("GBP", "£"):
        return int(amount * 105)
    elif currency in ("EUR", "€"):
        return int(amount * 90)
    elif currency in ("SGD",):
        return int(amount * 62)
    elif currency in ("AED",):
        return int(amount * 23)
    else:
        return int(amount)


def _row_to_job(row, country: str, now: str) -> dict | None:
    """Convert a JobSpy DataFrame row (as dict/Series) to our job dict."""
    title = str(row.get("title") or "").strip()
    job_url = str(row.get("job_url") or "").strip()
    if not title or not job_url or job_url in ("nan", "None"):
        return None

    description = str(row.get("description") or "")
    # Trim to 4000 chars max
    description_full = description[:4000]
    description_snippet = re.sub(r"\s+", " ", description[:350]).strip()

    # Salary
    min_inr = _to_annual_inr(
        row.get("min_amount"), str(row.get("interval") or ""), str(row.get("currency") or "")
    )
    max_inr = _to_annual_inr(
        row.get("max_amount"), str(row.get("interval") or ""), str(row.get("currency") or "")
    )
    salary_raw = ""
    if min_inr and max_inr:
        sal_l_min = round(min_inr / 100_000, 1)
        sal_l_max = round(max_inr / 100_000, 1)
        salary_raw = f"{sal_l_min}-{sal_l_max} LPA"
    elif min_inr:
        salary_raw = f"{round(min_inr / 100_000, 1)} LPA"

    # Experience — try to extract from description
    exp_text = ""
    exp_match = re.search(
        r"(\d+(?:\.\d+)?\s*[-–]\s*\d+(?:\.\d+)?|\d+\+?)\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp)",
        description, re.IGNORECASE,
    )
    if exp_match:
        exp_text = exp_match.group(0)
    exp_min, exp_max = parse_experience(exp_text) if exp_text else (None, None)

    # Location
    location = str(row.get("location") or "").strip()
    if row.get("is_remote"):
        location = location or "Remote"
        if "remote" not in location.lower():
            location = f"Remote / {location}" if location else "Remote"

    # Recruiter email from emails list or description
    emails_field = row.get("emails")
    recruiter_email = ""
    if emails_field and str(emails_field) not in ("nan", "None", "[]"):
        try:
            # Could be a list or string
            if isinstance(emails_field, list):
                recruiter_email = emails_field[0] if emails_field else ""
            else:
                recruiter_email = str(emails_field).strip("[]'\" ")
        except Exception:
            pass
    if not recruiter_email:
        found = extract_emails(description)
        recruiter_email = found[0] if found else ""

    # Source / site
    site = str(row.get("site") or "").lower()
    source = SITE_SOURCE_MAP.get(site, site or "jobspy")

    # Skills — try to pull from description keywords (rough extraction)
    skills_raw = _extract_skills_snippet(description)

    url_hash = make_url_hash(job_url)

    return {
        "title":               title,
        "company":             str(row.get("company") or "").strip(),
        "location":            location,
        "salary_min":          min_inr,
        "salary_max":          max_inr,
        "salary_raw":          salary_raw,
        "salary_target":       0,
        "experience_required": exp_text,
        "experience_min":      exp_min,
        "experience_max":      exp_max,
        "description":         description_full,
        "description_snippet": description_snippet,
        "skills_required":     skills_raw,
        "job_url":             job_url,
        "url_hash":            url_hash,
        "source":              source,
        "country":             country,
        "recruiter_name":      "",
        "recruiter_email":     recruiter_email,
        "status":              "new",
        "scraped_at":          now,
    }


# Common tech skill keywords to scan for in JDs
_SKILL_WORDS = [
    "python", "java", "javascript", "typescript", "react", "angular", "vue",
    "node", "nodejs", "django", "fastapi", "flask", "spring", "golang", "go",
    "rust", "c++", "c#", ".net", "ruby", "rails", "kotlin", "swift", "scala",
    "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform", "jenkins",
    "git", "ci/cd", "linux", "bash", "pandas", "numpy", "tensorflow", "pytorch",
    "machine learning", "deep learning", "llm", "nlp", "data science", "spark",
    "kafka", "airflow", "dbt", "tableau", "power bi", "excel",
    "html", "css", "graphql", "rest", "api", "microservices",
    "agile", "scrum", "product management", "figma",
]


def _extract_skills_snippet(description: str) -> str:
    """Pull recognized skill keywords from job description."""
    text = description.lower()
    found = [s for s in _SKILL_WORDS if re.search(r"\b" + re.escape(s) + r"\b", text)]
    return ", ".join(found[:20])


class JobSpyScraper(BaseScraper):
    """
    Wraps python-jobspy to scrape LinkedIn, Indeed, Glassdoor, Google Jobs.
    Each 'source' in the SCRAPERS dict maps to one call of this class
    targeting that specific site.
    """

    def __init__(self, sites: list[str] | None = None):
        self.sites = sites or ["linkedin", "indeed", "glassdoor", "google"]

    def search(self, role, location, locations, country, salary_target, experience_years):
        if sys.version_info < (3, 10):
            return [], "JobSpy requires Python 3.10+ (skipped)"

        try:
            from jobspy import scrape_jobs  # type: ignore
        except ImportError:
            return [], "python-jobspy not installed"

        now = datetime.now(timezone.utc).isoformat()
        all_jobs, error = [], None

        # Build location string for search
        search_loc = locations[0] if locations else location or ""
        if country == "IN" and not search_loc:
            search_loc = "India"

        indeed_country = INDEED_COUNTRY_MAP.get(country, "USA")

        # Google-specific search term includes location
        google_term = f"{role} jobs"
        if search_loc:
            google_term = f"{role} jobs in {search_loc}"

        try:
            df = scrape_jobs(
                site_name=self.sites,
                search_term=role,
                location=search_loc,
                results_wanted=25,
                hours_old=72,
                country_indeed=indeed_country,
                google_search_term=google_term,
                verbose=0,
            )
        except Exception as exc:
            return [], f"JobSpy scrape error: {exc}"

        if df is None or df.empty:
            return [], None

        seen_hashes = set()
        for _, row in df.iterrows():
            row_dict = row.where(row.notna(), other=None).to_dict()
            job = _row_to_job(row_dict, country, now)
            if job and job["url_hash"] not in seen_hashes:
                seen_hashes.add(job["url_hash"])
                all_jobs.append(job)

        return all_jobs, error
