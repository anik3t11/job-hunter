from __future__ import annotations
import requests
from datetime import datetime, timezone

from .base import BaseScraper
from .utils import get_headers, make_url_hash, extract_emails, parse_experience, parse_salary

NAUKRI_SALARY_SLABS = [
    (0, 100_000, 0),
    (100_001, 200_000, 1),
    (200_001, 300_000, 2),
    (300_001, 500_000, 3),
    (500_001, 700_000, 4),
    (700_001, 1_000_000, 5),
    (1_000_001, 1_500_000, 6),
    (1_500_001, 2_000_000, 7),
    (2_000_001, 3_000_000, 8),
    (3_000_001, 5_000_000, 9),
    (5_000_001, 10_000_000, 10),
    (10_000_001, 15_000_000, 11),
    (15_000_001, float("inf"), 12),
]


def _salary_to_slab(salary_target: int) -> int:
    # Use 70% of target as minimum slab (±30% flex)
    effective_min = int(salary_target * 0.70)
    for lo, hi, slab in NAUKRI_SALARY_SLABS:
        if lo <= effective_min <= hi:
            return max(0, slab - 1)  # one slab lower for flex
    return 0


class NaukriScraper(BaseScraper):
    API_URL = "https://www.naukri.com/jobapi/v3/search"
    MAX_PAGES = 5

    def search(self, role, location, locations, country, salary_target, experience_years):
        # Naukri is India-only; skip if searching other country
        if country not in ("IN", ""):
            return [], None

        jobs = []
        error = None
        now = datetime.now(timezone.utc).isoformat()
        salary_slab = _salary_to_slab(salary_target) if salary_target else 0
        exp_years = int(experience_years) if experience_years else 0

        search_locs = locations if locations else ([location] if location else [""])

        headers = {
            **get_headers(),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": "https://www.naukri.com/",
            "Origin": "https://www.naukri.com",
            "appid": "109",
            "SystemId": "Naukri",
            "gzip": "true",
        }

        for loc in search_locs[:3]:
            loc_jobs, loc_err = self._search_one(role, loc, salary_slab, exp_years, headers, now)
            jobs.extend(loc_jobs)
            if loc_err and not error:
                error = loc_err

        # Dedupe
        seen = set()
        unique = []
        for j in jobs:
            if j["url_hash"] not in seen:
                seen.add(j["url_hash"])
                unique.append(j)
        return unique, error

    def _search_one(self, role, location, salary_slab, exp_years, headers, now):
        jobs = []
        error = None
        for page in range(1, self.MAX_PAGES + 1):
            params = {
                "noOfResults": 20,
                "urlType": "search_by_key_loc",
                "searchType": "adv",
                "keyword": role,
                "location": location,
                "experience": exp_years,
                "pageNo": page,
                "src": "jobsearchDesk",
                "latLong": "",
            }
            if salary_slab:
                params["salary"] = salary_slab

            try:
                resp = requests.get(self.API_URL, headers=headers, params=params, timeout=15)
            except requests.RequestException as e:
                error = "Naukri request failed: {}".format(e)
                break

            if resp.status_code == 429:
                error = "Naukri rate limited."
                break
            if resp.status_code != 200:
                error = "Naukri returned HTTP {}".format(resp.status_code)
                break

            try:
                data = resp.json()
            except Exception:
                error = "Naukri returned non-JSON."
                break

            job_list = data.get("jobDetails", [])
            if not job_list:
                break

            for item in job_list:
                job = self._parse_item(item, now)
                if job:
                    jobs.append(job)

        return jobs, error

    def _parse_item(self, item, scraped_at):
        try:
            title = item.get("title", "").strip()
            company = item.get("companyName", "").strip()
            if not title or not company:
                return None

            placeholders = {
                p.get("label", "").lower(): p.get("value", "")
                for p in item.get("placeholders", [])
            }
            location = placeholders.get("location", "")
            salary_raw = placeholders.get("salary", "")
            exp_raw = placeholders.get("experience", "")

            salary_min, salary_max = parse_salary(salary_raw)
            if salary_min is None:
                s_min = item.get("minimumSalary")
                s_max = item.get("maximumSalary")
                salary_min = int(s_min) if s_min else None
                salary_max = int(s_max) if s_max else None

            exp_min, exp_max = parse_experience(exp_raw)
            if exp_min is None:
                e_min = item.get("minimumExperience")
                e_max = item.get("maximumExperience")
                exp_min = float(e_min) if e_min is not None else None
                exp_max = float(e_max) if e_max is not None else None

            description = item.get("jobDescription", "")
            tags = item.get("tagsAndSkills", "") or ""
            skills = ", ".join(tags.split(",")[:10])
            emails = extract_emails(description)

            jd_url = item.get("jdURL", "")
            job_url = "https://www.naukri.com{}".format(jd_url) if jd_url else ""
            if not job_url:
                return None

            return {
                "title": title,
                "company": company,
                "location": location,
                "country": "IN",
                "salary_raw": salary_raw,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "experience_required": exp_raw,
                "experience_min": exp_min,
                "experience_max": exp_max,
                "description": description,
                "skills_required": skills,
                "job_url": job_url,
                "recruiter_email": emails[0] if emails else None,
                "source": "naukri",
                "scraped_at": scraped_at,
                "url_hash": make_url_hash(job_url),
            }
        except Exception:
            return None
