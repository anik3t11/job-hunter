from __future__ import annotations
"""
Foundit (formerly Monster India) scraper.
India's largest job board. Uses their internal REST API.
"""
import requests
from datetime import datetime, timezone

from .base import BaseScraper
from .utils import get_headers, make_url_hash, extract_emails, parse_experience, parse_salary


class FounditScraper(BaseScraper):
    """
    Foundit (foundit.in) — India focused.
    Skipped automatically for non-IN country searches.
    """
    SEARCH_URL = "https://www.foundit.in/middleware/jobsearch/v2/search"
    MAX_PAGES = 4

    def search(self, role, location, locations, country, salary_target, experience_years):
        if country not in ("IN", ""):
            return [], None

        jobs = []
        error = None
        now = datetime.now(timezone.utc).isoformat()

        search_locs = locations if locations else ([location] if location else [""])

        headers = {
            **get_headers(),
            "Referer": "https://www.foundit.in/",
            "Origin": "https://www.foundit.in",
        }

        for loc in search_locs[:3]:
            loc_jobs, loc_err = self._search_one(role, loc, salary_target, experience_years, headers, now)
            jobs.extend(loc_jobs)
            if loc_err and not error:
                error = loc_err

        seen = set()
        unique = [j for j in jobs if not (j["url_hash"] in seen or seen.add(j["url_hash"]))]
        return unique, error

    def _search_one(self, role, location, salary_target, experience_years, headers, now):
        jobs = []
        error = None

        for page in range(self.MAX_PAGES):
            params = {
                "query": role,
                "locations": location,
                "experienceRanges": "{}~{}".format(
                    max(0, int(experience_years) - 1),
                    int(experience_years) + 3
                ),
                "start": page * 15,
                "rows": 15,
                "sort": "3",    # 3 = relevance
            }
            if salary_target:
                # Foundit uses annual salary in lakhs
                sal_lakh = max(1, int(salary_target * 0.70 / 100_000))
                params["minSalary"] = sal_lakh

            try:
                resp = requests.get(
                    self.SEARCH_URL, headers=headers, params=params, timeout=15
                )
            except requests.RequestException as e:
                error = "Foundit request failed: {}".format(e)
                break

            if resp.status_code == 429:
                error = "Foundit rate limited."
                break
            if resp.status_code != 200:
                error = "Foundit returned HTTP {}".format(resp.status_code)
                break

            try:
                data = resp.json()
            except Exception:
                error = "Foundit returned non-JSON."
                break

            job_list = data.get("jobDetails", data.get("data", {}).get("jobDetails", []))
            if not job_list:
                break

            for item in job_list:
                job = self._parse_item(item, now)
                if job:
                    jobs.append(job)

        return jobs, error

    def _parse_item(self, item, scraped_at):
        try:
            title = (item.get("title") or item.get("jobTitle") or "").strip()
            company = (item.get("companyName") or item.get("company") or "").strip()
            if not title:
                return None

            location = item.get("location", item.get("jobLocation", ""))
            if isinstance(location, list):
                location = ", ".join(location)

            salary_raw = item.get("salaryLabel", item.get("salary", ""))
            salary_min, salary_max = parse_salary(str(salary_raw) if salary_raw else "")

            exp_raw = item.get("experienceLabel", item.get("experience", ""))
            exp_min, exp_max = parse_experience(str(exp_raw) if exp_raw else "")

            description = item.get("jobDescription", item.get("description", ""))
            skills_list = item.get("keySkills", item.get("skills", []))
            if isinstance(skills_list, list):
                skills = ", ".join(skills_list[:10])
            else:
                skills = str(skills_list)[:200]

            # Build job URL
            job_id = item.get("jobId", item.get("id", ""))
            slug = item.get("jobSlug", "")
            if slug:
                job_url = "https://www.foundit.in/job/{}".format(slug)
            elif job_id:
                job_url = "https://www.foundit.in/job/{}".format(job_id)
            else:
                return None

            emails = extract_emails(description)

            return {
                "title": title,
                "company": company or "Unknown",
                "location": location,
                "country": "IN",
                "salary_raw": str(salary_raw),
                "salary_min": salary_min,
                "salary_max": salary_max,
                "experience_required": str(exp_raw),
                "experience_min": exp_min,
                "experience_max": exp_max,
                "description": description,
                "skills_required": skills,
                "job_url": job_url,
                "recruiter_email": emails[0] if emails else None,
                "source": "foundit",
                "scraped_at": scraped_at,
                "url_hash": make_url_hash(job_url),
            }
        except Exception:
            return None
