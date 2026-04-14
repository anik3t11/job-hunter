from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.database import insert_jobs, get_settings, save_settings
from backend.scrapers.linkedin import LinkedInScraper
from backend.scrapers.naukri import NaukriScraper
from backend.scrapers.wellfound import WellfoundScraper
from backend.scrapers.indeed import IndeedScraper
from backend.scrapers.foundit import FounditScraper
from backend.services.matcher import score_and_attach
from backend.services.role_expander import expand_role

router = APIRouter(prefix="/api/search", tags=["search"])

SCRAPERS = {
    "linkedin":  LinkedInScraper(),
    "naukri":    NaukriScraper(),
    "wellfound": WellfoundScraper(),
    "indeed":    IndeedScraper(),
    "foundit":   FounditScraper(),
}


class SearchRequest(BaseModel):
    role: str
    locations: list = []
    country: str = "IN"
    salary_target: Optional[int] = 0
    experience_years: Optional[float] = 0
    sources: list = ["linkedin", "naukri", "indeed"]


@router.post("")
def run_search(req: SearchRequest):
    settings = get_settings()
    save_settings({
        "last_search_role": req.role,
        "last_search_country": req.country,
    })
    settings["last_search_role"] = req.role
    settings["last_search_country"] = req.country
    settings["last_search_locations"] = ",".join(req.locations)

    valid_sources = [s for s in req.sources if s in SCRAPERS]
    location_str = ", ".join(req.locations) if req.locations else ""

    # Expand role into cluster variants — search all related titles
    role_variants = expand_role(req.role, max_variants=4)  # original + up to 4 related

    all_jobs = []
    errors = []
    seen_hashes = set()

    def run_scraper(source: str, role_variant: str):
        scraper = SCRAPERS[source]
        jobs, err = scraper.search(
            role=role_variant,
            location=location_str,
            locations=req.locations,
            country=req.country,
            salary_target=req.salary_target or 0,
            experience_years=req.experience_years or 0,
        )
        # Tag each job with which variant found it
        for job in jobs:
            if role_variant.lower() != req.role.lower():
                job["role_variant"] = role_variant
        return source, role_variant, jobs, err

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {}
        for src in valid_sources:
            for variant in role_variants:
                futures[executor.submit(run_scraper, src, variant)] = (src, variant)

        for future in as_completed(futures):
            source, variant, jobs, err = future.result()
            if err:
                # Only record error once per source (not per variant)
                if not any(e["source"] == source for e in errors):
                    errors.append({"source": source, "message": err})
            for job in jobs:
                url_hash = job.get("url_hash", "")
                if url_hash and url_hash in seen_hashes:
                    continue
                if url_hash:
                    seen_hashes.add(url_hash)
                scored = score_and_attach(job, settings)
                all_jobs.append(scored)

    total_inserted = total_skipped = 0
    if all_jobs:
        total_inserted, total_skipped = insert_jobs(all_jobs)

    return {
        "jobs_found": len(all_jobs),
        "jobs_new": total_inserted,
        "jobs_duplicate": total_skipped,
        "role_variants_searched": role_variants,
        "errors": errors,
    }
