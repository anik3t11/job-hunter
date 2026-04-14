from __future__ import annotations
"""
Ambitionbox scraper — company salary + ratings for Indian job market.
Caches results for 7 days to avoid hammering the site.
"""
import re
import time
import requests
from datetime import datetime, timezone, timedelta

from backend.database import get_company_cache, save_company_cache

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}

CACHE_DAYS = 7


def _slug(name: str) -> str:
    """Convert company name to URL-friendly slug."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower().strip()).strip("-")


def _cache_fresh(cached_at: str) -> bool:
    try:
        dt = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt) < timedelta(days=CACHE_DAYS)
    except Exception:
        return False


def get_company_insights(company_name: str, role: str = "") -> dict:
    """
    Return salary range, rating, and review summary for a company.
    Uses cache first; scrapes Ambitionbox if stale.
    """
    slug = _slug(company_name)
    role_key = _slug(role) if role else ""

    # Try cache
    cached = get_company_cache(slug, role_key)
    if cached and _cache_fresh(cached.get("cached_at", "")):
        return _format_insights(cached)

    # Scrape
    data = _scrape_ambitionbox(slug, company_name, role)
    if data:
        data["company_slug"] = slug
        data["role"] = role_key
        save_company_cache(data)
        return _format_insights(data)

    return {}


def _format_insights(data: dict) -> dict:
    sal_min = data.get("avg_salary_min")
    sal_max = data.get("avg_salary_max")
    salary_str = ""
    if sal_min and sal_max:
        salary_str = "₹{:.1f}L – ₹{:.1f}L".format(sal_min / 100000, sal_max / 100000)
    elif sal_min:
        salary_str = "~₹{:.1f}L".format(sal_min / 100000)

    return {
        "salary_range":    salary_str,
        "avg_salary_min":  data.get("avg_salary_min"),
        "avg_salary_max":  data.get("avg_salary_max"),
        "rating":          data.get("rating"),
        "review_count":    data.get("review_count", 0),
        "review_summary":  data.get("review_summary", ""),
    }


def _scrape_ambitionbox(slug: str, company_name: str, role: str = "") -> dict | None:
    """Scrape Ambitionbox company page for salary + rating."""
    try:
        url = "https://www.ambitionbox.com/overview/{}-overview".format(slug)
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            # Try alternate slug formats
            alt_slug = company_name.lower().replace(" ", "-").replace(".", "").replace(",", "")
            url = "https://www.ambitionbox.com/overview/{}-overview".format(alt_slug)
            resp = requests.get(url, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                return None

        html = resp.text
        result = {"source": "ambitionbox"}

        # Extract rating
        rating_m = re.search(r'"ratingValue"\s*:\s*"?(\d+(?:\.\d+)?)"?', html)
        if not rating_m:
            rating_m = re.search(r'class="[^"]*rating[^"]*"[^>]*>\s*(\d+\.\d+)', html)
        if rating_m:
            try:
                result["rating"] = float(rating_m.group(1))
            except Exception:
                pass

        # Extract review count
        review_m = re.search(r'(\d[\d,]+)\s*(?:reviews?|ratings?)', html, re.I)
        if review_m:
            result["review_count"] = int(review_m.group(1).replace(",", ""))

        # Extract salary data
        result.update(_scrape_salary(slug, company_name, role))

        # Extract a review snippet as summary
        review_m = re.search(
            r'"pros"\s*:\s*"([^"]{20,200})"', html
        )
        if not review_m:
            review_m = re.search(r'class="[^"]*review[^"]*"[^>]*>\s*<[^>]+>([^<]{20,200})', html)
        if review_m:
            result["review_summary"] = review_m.group(1).strip()

        return result if len(result) > 1 else None

    except Exception as e:
        print("[ambitionbox] scrape error for {}: {}".format(company_name, e))
        return None


def _scrape_salary(slug: str, company_name: str, role: str = "") -> dict:
    """Scrape salary page from Ambitionbox."""
    try:
        role_slug = _slug(role) if role else ""
        if role_slug:
            url = "https://www.ambitionbox.com/salaries/{}-salaries/{}".format(slug, role_slug)
        else:
            url = "https://www.ambitionbox.com/salaries/{}-salaries".format(slug)

        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return {}

        html = resp.text

        # Look for salary ranges in JSON-LD or visible text
        # Pattern: ₹X - ₹Y Lakhs or X LPA - Y LPA
        patterns = [
            r'(\d+(?:\.\d+)?)\s*[Ll](?:akhs?|PA)?\s*[-–to]+\s*(\d+(?:\.\d+)?)\s*[Ll](?:akhs?|PA)?',
            r'₹\s*(\d+(?:\.\d+)?)\s*[-–]\s*₹\s*(\d+(?:\.\d+)?)',
            r'"minValue"\s*:\s*(\d+).*?"maxValue"\s*:\s*(\d+)',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.I)
            if m:
                try:
                    low  = float(m.group(1))
                    high = float(m.group(2))
                    # If values look like lakhs (< 200), convert to absolute
                    if low < 200:
                        low  *= 100000
                        high *= 100000
                    return {"avg_salary_min": int(low), "avg_salary_max": int(high)}
                except Exception:
                    continue
        return {}
    except Exception:
        return {}
