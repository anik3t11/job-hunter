from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.database import insert_jobs, get_settings, save_settings
from backend.scrapers.linkedin  import LinkedInScraper
from backend.scrapers.naukri    import NaukriScraper
from backend.scrapers.wellfound import WellfoundScraper
from backend.scrapers.indeed    import IndeedScraper
from backend.scrapers.foundit   import FounditScraper
from backend.services.matcher   import score_and_attach
from backend.services.role_expander import expand_role
from backend.services.auth_service  import get_current_user

router = APIRouter(prefix="/api/search", tags=["search"])

SCRAPERS = {
    "linkedin":  LinkedInScraper(),
    "naukri":    NaukriScraper(),
    "wellfound": WellfoundScraper(),
    "indeed":    IndeedScraper(),
    "foundit":   FounditScraper(),
}

# Indian city/state keywords for geography enforcement
INDIA_KEYWORDS = {
    "india", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "pune",
    "chennai", "kolkata", "ahmedabad", "surat", "jaipur", "noida", "gurugram",
    "gurgaon", "lucknow", "indore", "bhopal", "chandigarh", "kochi", "coimbatore",
    "nagpur", "visakhapatnam", "vadodara", "remote", "pan india", "work from home",
    "wfh", "hybrid", "anywhere in india",
}


def _is_india_job(job: dict) -> bool:
    loc = (job.get("location") or "").lower()
    country = (job.get("country") or "").upper()
    if country and country != "IN":
        return False
    return any(kw in loc for kw in INDIA_KEYWORDS) or not loc


class SearchRequest(BaseModel):
    role:             str
    locations:        list  = []
    country:          str   = "IN"
    salary_target:    Optional[int]   = 0
    experience_years: Optional[float] = 0
    sources:          list  = ["linkedin", "naukri", "indeed"]


@router.post("")
def run_search(req: SearchRequest, user: dict = Depends(get_current_user)):
    uid      = user["user_id"]
    settings = get_settings(uid)
    save_settings(uid, {"last_search_role": req.role, "last_search_country": req.country})
    settings["last_search_role"]      = req.role
    settings["last_search_country"]   = req.country
    settings["last_search_locations"] = ",".join(req.locations)

    valid_sources = [s for s in req.sources if s in SCRAPERS]
    location_str  = ", ".join(req.locations) if req.locations else ""
    role_variants = expand_role(req.role, max_variants=4)

    all_jobs, errors, seen_hashes = [], [], set()

    def run_scraper(source: str, variant: str):
        scraper = SCRAPERS[source]
        jobs, err = scraper.search(
            role=variant, location=location_str,
            locations=req.locations, country=req.country,
            salary_target=req.salary_target or 0,
            experience_years=req.experience_years or 0,
        )
        for job in jobs:
            if variant.lower() != req.role.lower():
                job["role_variant"] = variant
        return source, variant, jobs, err

    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {
            ex.submit(run_scraper, src, var): (src, var)
            for src in valid_sources
            for var in role_variants
        }
        for future in as_completed(futures):
            source, variant, jobs, err = future.result()
            if err and not any(e["source"] == source for e in errors):
                errors.append({"source": source, "message": err})
            for job in jobs:
                # Geography enforcement
                if req.country == "IN" and not _is_india_job(job):
                    continue
                url_hash = job.get("url_hash", "")
                if url_hash and url_hash in seen_hashes:
                    continue
                if url_hash:
                    seen_hashes.add(url_hash)
                all_jobs.append(score_and_attach(job, settings))

    inserted = skipped = 0
    if all_jobs:
        inserted, skipped = insert_jobs(all_jobs, uid)

    return {
        "jobs_found":            len(all_jobs),
        "jobs_new":              inserted,
        "jobs_duplicate":        skipped,
        "role_variants_searched": role_variants,
        "errors":                errors,
    }
