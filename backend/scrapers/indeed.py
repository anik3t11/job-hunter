from __future__ import annotations
"""
Indeed scraper — country-aware via subdomain routing.
Uses Indeed's publicly accessible job search pages.
"""
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

from .base import BaseScraper
from .utils import get_headers, polite_sleep, make_url_hash, extract_emails, parse_experience, parse_salary

# Indeed subdomain per country
INDEED_DOMAINS = {
    "IN": "in.indeed.com",
    "US": "www.indeed.com",
    "GB": "uk.indeed.com",
    "CA": "ca.indeed.com",
    "AU": "au.indeed.com",
    "SG": "sg.indeed.com",
    "AE": "ae.indeed.com",
    "DE": "de.indeed.com",
    "NL": "nl.indeed.com",
    "JP": "jp.indeed.com",
}


class IndeedScraper(BaseScraper):
    MAX_PAGES = 3   # 15 jobs/page × 3 = 45

    def search(self, role, location, locations, country, salary_target, experience_years):
        domain = INDEED_DOMAINS.get(country, "www.indeed.com")
        base_url = "https://{}/jobs".format(domain)
        jobs = []
        error = None
        now = datetime.now(timezone.utc).isoformat()

        search_locs = locations if locations else ([location] if location else [""])

        for loc in search_locs[:3]:
            loc_jobs, loc_err = self._search_one(base_url, role, loc, country, now)
            jobs.extend(loc_jobs)
            if loc_err and not error:
                error = loc_err

        # Dedupe
        seen = set()
        unique = [j for j in jobs if not (j["url_hash"] in seen or seen.add(j["url_hash"]))]
        return unique, error

    def _search_one(self, base_url, role, location, country, now):
        jobs = []
        error = None

        for page in range(self.MAX_PAGES):
            params = {
                "q": role,
                "l": location,
                "start": page * 15,
                "fromage": "30",   # last 30 days
                "sort": "date",
            }
            headers = {
                **get_headers(),
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://{}".format(INDEED_DOMAINS.get(country, "www.indeed.com")),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            try:
                resp = requests.get(base_url, headers=headers, params=params, timeout=15)
            except requests.RequestException as e:
                error = "Indeed request failed: {}".format(e)
                break

            if resp.status_code in (403, 429):
                # Try RSS feed as fallback
                rss_jobs = self._try_rss(base_url, params, country, now)
                if rss_jobs:
                    jobs.extend(rss_jobs)
                else:
                    error = "Indeed blocked the request. Try again later."
                break
            if resp.status_code != 200:
                error = "Indeed returned HTTP {}".format(resp.status_code)
                break

            soup = BeautifulSoup(resp.text, "lxml")

            # Indeed renders job cards with class="job_seen_beacon" or "resultContent"
            cards = soup.find_all("div", class_=re.compile(r"job_seen_beacon|resultContent|slider_item"))
            if not cards:
                # Try alternate card selector
                cards = soup.find_all("td", class_="resultContent")
            if not cards:
                break

            for card in cards:
                job = self._parse_card(card, base_url, country, now)
                if job:
                    jobs.append(job)

            polite_sleep(2.0, 3.5)

        return jobs, error

    def _try_rss(self, base_url, params, country, now):
        """Fallback: use Indeed RSS feed when HTML is blocked."""
        try:
            domain = INDEED_DOMAINS.get(country, "www.indeed.com")
            rss_url = "https://{}/rss?q={}&l={}&sort=date".format(
                domain, params.get("q", ""), params.get("l", "")
            )
            resp = requests.get(rss_url, headers=get_headers(), timeout=15)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.text, "lxml-xml")
            jobs = []
            for item in soup.find_all("item")[:20]:
                title   = item.find("title")
                link    = item.find("link")
                company = item.find("source")
                desc    = item.find("description")
                if not title or not link:
                    continue
                jobs.append({
                    "title": title.get_text(strip=True),
                    "company": company.get_text(strip=True) if company else "",
                    "location": params.get("l", ""),
                    "salary_min": None, "salary_max": None, "salary_raw": "",
                    "salary_target": None, "experience_required": "",
                    "description": BeautifulSoup(desc.get_text(), "lxml").get_text(strip=True)[:500] if desc else "",
                    "description_snippet": "",
                    "skills_required": "", "recruiter_name": "", "recruiter_email": "",
                    "job_url": link.get_text(strip=True),
                    "url_hash": make_url_hash(link.get_text(strip=True)),
                    "source": "indeed", "country": country, "scraped_at": now,
                })
            return jobs
        except Exception:
            return []

    def _parse_card(self, card, base_url, country, scraped_at):
        try:
            # Title
            title_tag = card.find("a", class_=re.compile(r"jcs-JobTitle|jobtitle|jobTitle"))
            if not title_tag:
                title_tag = card.find("h2", class_=re.compile(r"jobTitle"))
            if not title_tag:
                return None

            title = title_tag.get_text(strip=True)
            title = re.sub(r"^(new\s*)?", "", title, flags=re.I).strip()

            # Job URL
            href = title_tag.get("href", "") or (title_tag.find("a") or {}).get("href", "")
            if not href:
                return None
            if href.startswith("/"):
                domain = re.search(r"https?://([^/]+)", base_url)
                job_url = "https://{}{}".format(domain.group(1) if domain else "www.indeed.com", href.split("?")[0])
            else:
                job_url = href.split("?")[0]

            # Company
            company_tag = card.find(class_=re.compile(r"companyName|company(?!.*location)"))
            company = company_tag.get_text(strip=True) if company_tag else "Unknown"

            # Location
            loc_tag = card.find(class_=re.compile(r"companyLocation"))
            location = loc_tag.get_text(strip=True) if loc_tag else ""

            # Salary
            sal_tag = card.find(class_=re.compile(r"salary-snippet|metadata.*salary"))
            salary_raw = sal_tag.get_text(strip=True) if sal_tag else ""
            salary_min, salary_max = parse_salary(salary_raw)

            return {
                "title": title,
                "company": company,
                "location": location,
                "country": country,
                "salary_raw": salary_raw,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "experience_required": "",
                "experience_min": None,
                "experience_max": None,
                "description": "",
                "skills_required": "",
                "job_url": job_url,
                "recruiter_email": None,
                "source": "indeed",
                "scraped_at": scraped_at,
                "url_hash": make_url_hash(job_url),
            }
        except Exception:
            return None
