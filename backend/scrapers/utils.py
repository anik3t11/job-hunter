from __future__ import annotations
import re
import hashlib
import random
import time

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

JUNK_EMAILS = {"noreply", "no-reply", "support", "help", "legal", "privacy", "contact", "info", "hello", "admin"}

CITY_ALIASES = {
    "bangalore": ["bengaluru", "blr"],
    "bengaluru": ["bangalore", "blr"],
    "mumbai": ["bombay"],
    "delhi": ["new delhi", "ncr", "delhi ncr"],
    "hyderabad": ["hyd", "cyberabad"],
    "chennai": ["madras"],
    "kolkata": ["calcutta"],
    "pune": ["pun"],
}


def get_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }


def polite_sleep(min_s: float = 1.0, max_s: float = 2.5):
    time.sleep(random.uniform(min_s, max_s))


def make_url_hash(url: str) -> str:
    return hashlib.md5(url.strip().encode()).hexdigest()


def extract_emails(text: str) -> list:
    if not text:
        return []
    found = re.findall(r"[\w.+\-]+@[\w\-]+\.[\w.]+", text)
    result = []
    for email in found:
        local = email.split("@")[0].lower()
        if not any(junk in local for junk in JUNK_EMAILS):
            result.append(email.lower())
    return list(dict.fromkeys(result))


def parse_experience(text: str) -> tuple:
    if not text:
        return None, None
    text = text.lower()

    m = re.search(r"(\d+(?:\.\d+)?)\s*[-\u2013to]+\s*(\d+(?:\.\d+)?)", text)
    if m:
        return float(m.group(1)), float(m.group(2))

    m = re.search(r"(\d+(?:\.\d+)?)\s*\+", text)
    if m:
        val = float(m.group(1))
        return val, val + 5

    m = re.search(r"(?:minimum|at least|min\.?)\s*(\d+(?:\.\d+)?)", text)
    if m:
        val = float(m.group(1))
        return val, val + 5

    if re.search(r"fresher|entry.?level|0 year", text):
        return 0.0, 1.0

    m = re.search(r"(\d+(?:\.\d+)?)", text)
    if m:
        val = float(m.group(1))
        return val, val
    return None, None


def parse_salary(text: str) -> tuple:
    if not text:
        return None, None
    text = text.replace(",", "").lower()

    m = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:lpa|l|lakh)?\s*[-\u2013to]+\s*(\d+(?:\.\d+)?)\s*(?:lpa|l|lakh)",
        text,
    )
    if m:
        return int(float(m.group(1)) * 100_000), int(float(m.group(2)) * 100_000)

    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:lpa|l|lakh)", text)
    if m:
        val = int(float(m.group(1)) * 100_000)
        return val, val

    m = re.search(
        r"\$?(\d+(?:\.\d+)?)\s*k?\s*[-\u2013to]+\s*\$?(\d+(?:\.\d+)?)\s*k", text
    )
    if m:
        return int(float(m.group(1)) * 1000 * 83), int(float(m.group(2)) * 1000 * 83)

    m = re.search(r"(\d{4,})\s*(?:per month|\/month|pm)", text)
    if m:
        val = int(m.group(1)) * 12
        return val, val

    m = re.search(r"(\d{6,})\s*[-\u2013to]+\s*(\d{6,})", text)
    if m:
        return int(m.group(1)), int(m.group(2))

    m = re.search(r"(\d{6,})", text)
    if m:
        return int(m.group(1)), int(m.group(1))

    return None, None


def location_matches(job_location: str, preferred: str) -> bool:
    jl = job_location.lower()
    pref = preferred.lower().strip()
    if pref in jl:
        return True
    for alias in CITY_ALIASES.get(pref, []):
        if alias in jl:
            return True
    for canonical, aliases_list in CITY_ALIASES.items():
        if pref in aliases_list and canonical in jl:
            return True
    return False
