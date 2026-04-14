from __future__ import annotations
"""
Recruiter contact finder.
When a job has no recruiter email, try to find one via:
1. Common email patterns (firstname.lastname@company.com)
2. Google search for company HR/recruiter on LinkedIn
"""
import re
import requests
from fastapi import APIRouter, Depends, Query
from urllib.parse import unquote, quote_plus
from backend.services.auth_service import get_current_user

router = APIRouter(prefix="/api/recruiter", tags=["recruiter"])

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    )
}

COMMON_PATTERNS = [
    "{first}.{last}@{domain}",
    "{first}{last}@{domain}",
    "{f}{last}@{domain}",
    "hr@{domain}",
    "careers@{domain}",
    "recruitment@{domain}",
    "talent@{domain}",
    "hiring@{domain}",
]


def _company_domain(company_name: str) -> str:
    """Guess company email domain from name."""
    slug = re.sub(r"[^a-z0-9]", "", company_name.lower())
    return "{}.com".format(slug)


def _generate_email_patterns(first: str, last: str, domain: str) -> list:
    first = first.lower().strip()
    last  = last.lower().strip()
    f     = first[0] if first else ""
    results = []
    for pat in COMMON_PATTERNS:
        try:
            email = pat.format(first=first, last=last, f=f, domain=domain)
            if "@" in email and "." in email.split("@")[1]:
                results.append(email)
        except Exception:
            continue
    return results


def _search_linkedin_recruiters(company_name: str, role: str = "") -> list:
    """Google search for LinkedIn recruiter profiles at the company."""
    query = 'site:linkedin.com/in "{}" ("HR" OR "recruiter" OR "talent acquisition" OR "hiring")'.format(company_name)
    candidates = []
    try:
        resp = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query, "b": ""},
            headers=HEADERS, timeout=12,
        )
        resp.raise_for_status()
        links = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', resp.text, re.S)
        snippets = re.findall(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', resp.text, re.S)

        for i, (href, title) in enumerate(links[:5]):
            uddg = re.search(r"uddg=([^&]+)", href)
            real_url = unquote(uddg.group(1)) if uddg else href
            if "linkedin.com/in/" not in real_url:
                continue
            title_clean = re.sub(r"<[^>]+>", "", title).strip()
            snip = re.sub(r"<[^>]+>", "", snippets[i] if i < len(snippets) else "").strip()

            # Extract name from title (usually "Name - Title at Company | LinkedIn")
            name_match = re.match(r"^([A-Za-z ]{3,40})\s*[-|]", title_clean)
            name = name_match.group(1).strip() if name_match else title_clean[:30]

            # Try to generate email guesses
            name_parts = name.split()
            domain = _company_domain(company_name)
            emails = []
            if len(name_parts) >= 2:
                emails = _generate_email_patterns(name_parts[0], name_parts[-1], domain)

            candidates.append({
                "name":        name,
                "profile_url": real_url,
                "snippet":     snip[:200],
                "email_guesses": emails[:4],
            })

    except Exception as e:
        print("[recruiter] LinkedIn search error:", e)

    return candidates


@router.get("/find")
def find_recruiter(
    company: str = Query(...),
    role:    str = Query(default=""),
    user:    dict = Depends(get_current_user),
):
    """Find recruiter contacts for a company."""
    if not company or len(company) < 2:
        return {"error": "Company name required"}

    # LinkedIn profile search
    candidates = _search_linkedin_recruiters(company, role)

    # Always add generic HR email guesses for the company domain
    domain = _company_domain(company)
    generic_emails = [
        "hr@{}".format(domain),
        "careers@{}".format(domain),
        "recruitment@{}".format(domain),
        "talent@{}".format(domain),
    ]

    return {
        "company":       company,
        "domain":        domain,
        "candidates":    candidates,
        "generic_emails": generic_emails,
    }
