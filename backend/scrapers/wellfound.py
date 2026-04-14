from __future__ import annotations
"""
Wellfound (formerly AngelList Talent) scraper.
Requires Playwright: pip install playwright && playwright install chromium
"""
from datetime import datetime, timezone
from .base import BaseScraper
from .utils import make_url_hash, parse_salary

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class WellfoundScraper(BaseScraper):

    def search(self, role, location, locations, country, salary_target, experience_years):
        if not PLAYWRIGHT_AVAILABLE:
            return [], (
                "Wellfound requires Playwright. "
                "Run: pip install playwright && playwright install chromium"
            )
        loc = locations[0] if locations else location
        return self._scrape_with_playwright(role, loc)

    def _scrape_with_playwright(self, role, location):
        jobs = []
        error = None
        now = datetime.now(timezone.utc).isoformat()

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                role_encoded = role.replace(" ", "-").lower()
                loc_encoded = location.replace(" ", "-").lower()
                url = "https://wellfound.com/jobs?q={}&l={}".format(role_encoded, loc_encoded)
                page.goto(url, timeout=20000, wait_until="networkidle")

                if page.locator("text=Sign up to see").count() > 0:
                    browser.close()
                    return [], "Wellfound requires login to show results."

                for _ in range(3):
                    page.keyboard.press("End")
                    page.wait_for_timeout(1500)

                cards = page.locator("[data-test='JobListing']").all()
                for card in cards[:50]:
                    try:
                        job = self._parse_card(card, now)
                        if job:
                            jobs.append(job)
                    except Exception:
                        continue

                browser.close()
        except Exception as e:
            if "PlaywrightTimeout" in type(e).__name__:
                error = "Wellfound timed out."
            else:
                error = "Wellfound scraper error: {}".format(e)

        return jobs, error

    def _parse_card(self, card, scraped_at: str):
        try:
            title = card.locator("h2").first.inner_text(timeout=2000).strip()
            company = card.locator("h3").first.inner_text(timeout=2000).strip()

            location = ""
            loc_el = card.locator(".location, [data-test='LocationTag']").first
            if loc_el.count():
                location = loc_el.inner_text(timeout=2000).strip()

            salary_raw = ""
            sal_el = card.locator(".compensation, [data-test='SalaryTag']").first
            if sal_el.count():
                salary_raw = sal_el.inner_text(timeout=2000).strip()

            href = card.locator("a").first.get_attribute("href", timeout=2000) or ""
            job_url = "https://wellfound.com{}".format(href) if href.startswith("/") else href
            if not job_url:
                return None

            salary_min, salary_max = parse_salary(salary_raw)

            return {
                "title": title or "Unknown",
                "company": company or "Unknown",
                "location": location,
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
                "source": "wellfound",
                "scraped_at": scraped_at,
                "url_hash": make_url_hash(job_url),
            }
        except Exception:
            return None
