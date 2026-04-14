from __future__ import annotations
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

from .base import BaseScraper
from .utils import get_headers, polite_sleep, make_url_hash, extract_emails, parse_experience

# LinkedIn country code → geo_id mapping for major markets
COUNTRY_GEO_IDS = {
    "IN": "102713980",   # India
    "US": "103644278",   # United States
    "GB": "101165590",   # United Kingdom
    "CA": "101174742",   # Canada
    "AU": "101452733",   # Australia
    "SG": "102454443",   # Singapore
    "AE": "104305776",   # UAE
    "DE": "101282230",   # Germany
    "NL": "102890719",   # Netherlands
    "JP": "101355337",   # Japan
}


class LinkedInScraper(BaseScraper):
    SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    MAX_PAGES = 4

    def search(self, role, location, locations, country, salary_target, experience_years):
        jobs = []
        error = None
        now = datetime.now(timezone.utc).isoformat()

        # Run one search per location if multiple provided, else one search
        search_locations = locations if locations else ([location] if location else [""])

        for loc in search_locations[:3]:  # cap at 3 locations per source
            loc_jobs, loc_err = self._search_one_location(role, loc, country, now)
            jobs.extend(loc_jobs)
            if loc_err and not error:
                error = loc_err

        # Dedupe by url_hash within this batch
        seen = set()
        unique = []
        for j in jobs:
            if j["url_hash"] not in seen:
                seen.add(j["url_hash"])
                unique.append(j)

        return unique, error

    def _search_one_location(self, role, location, country, now):
        jobs = []
        error = None
        geo_id = COUNTRY_GEO_IDS.get(country, "")

        for page in range(self.MAX_PAGES):
            params = {
                "keywords": role,
                "location": location,
                "start": page * 25,
                "count": 25,
                "f_TPR": "r2592000",
            }
            if geo_id:
                params["geoId"] = geo_id

            try:
                resp = requests.get(
                    self.SEARCH_URL,
                    headers=get_headers(),
                    params=params,
                    timeout=15,
                )
            except requests.RequestException as e:
                error = "LinkedIn request failed: {}".format(e)
                break

            if resp.status_code == 429:
                error = "LinkedIn rate limited. Try again later."
                break
            if resp.status_code in (403, 401) or "authwall" in resp.url:
                error = "LinkedIn requires login for this search."
                break
            if resp.status_code != 200:
                error = "LinkedIn returned HTTP {}".format(resp.status_code)
                break

            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.find_all("li")
            if not cards:
                break

            for card in cards:
                job = self._parse_card(card, now, country)
                if job:
                    jobs.append(job)

            polite_sleep(1.5, 2.5)

        return jobs, error

    def _parse_card(self, card, scraped_at, country):
        try:
            title_tag = card.find(class_="base-search-card__title")
            company_tag = card.find(class_="base-search-card__subtitle")
            location_tag = card.find(class_="job-search-card__location")
            link_tag = card.find("a", class_="base-card__full-link")

            if not title_tag or not link_tag:
                return None

            title = title_tag.get_text(strip=True)
            company = company_tag.get_text(strip=True) if company_tag else "Unknown"
            location = location_tag.get_text(strip=True) if location_tag else ""
            job_url = link_tag["href"].split("?")[0]

            m = re.search(r"/view/(\d+)", job_url)
            job_id = m.group(1) if m else None

            description, recruiter_email, exp_raw = "", None, ""
            if job_id:
                description, recruiter_email, exp_raw = self._fetch_detail(job_id)

            exp_min, exp_max = parse_experience(exp_raw)

            return {
                "title": title,
                "company": company,
                "location": location,
                "country": country,
                "salary_raw": "",
                "salary_min": None,
                "salary_max": None,
                "experience_required": exp_raw,
                "experience_min": exp_min,
                "experience_max": exp_max,
                "description": description,
                "skills_required": "",
                "job_url": job_url,
                "recruiter_email": recruiter_email,
                "source": "linkedin",
                "scraped_at": scraped_at,
                "url_hash": make_url_hash(job_url),
            }
        except Exception:
            return None

    def _fetch_detail(self, job_id):
        try:
            url = self.DETAIL_URL.format(job_id=job_id)
            resp = requests.get(url, headers=get_headers(), timeout=10)
            if resp.status_code != 200:
                return "", None, ""

            soup = BeautifulSoup(resp.text, "lxml")
            desc_tag = soup.find(class_="show-more-less-html__markup")
            description = desc_tag.get_text(" ", strip=True) if desc_tag else ""

            emails = extract_emails(description)
            recruiter_email = emails[0] if emails else None

            criteria = soup.find_all(class_="description__job-criteria-text")
            exp_raw = ""
            for c in criteria:
                text = c.get_text(strip=True)
                if re.search(r"\d+.*(year|yr)", text, re.I):
                    exp_raw = text
                    break

            polite_sleep(0.5, 1.2)
            return description, recruiter_email, exp_raw
        except Exception:
            return "", None, ""
