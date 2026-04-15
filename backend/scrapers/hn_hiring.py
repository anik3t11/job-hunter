from __future__ import annotations
"""
Hacker News 'Who is Hiring' scraper.
Uses Algolia HN Search API — free, no auth required.
Fetches the latest monthly HN hiring thread and extracts job posts.
"""
import re
import requests
from datetime import datetime, timezone

HN_API = "https://hn.algolia.com/api/v1"

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def _extract_email(text):
    m = re.search(r"[\w.+\-]+@[\w\-]+\.[\w.]+", text or "")
    return m.group(0).lower() if m else ""

def _extract_url(text):
    m = re.search(r"https?://[^\s\"'>]{10,}", text or "")
    return m.group(0) if m else ""

def scrape_hn_hiring(role: str, country: str = "IN", max_results: int = 30) -> list:
    """Fetch HN Who Is Hiring posts matching the role."""
    posts = []
    try:
        # Find the latest "Who is Hiring" thread
        resp = requests.get(
            f"{HN_API}/search_by_date",
            params={
                "tags": "ask_hn,story",
                "query": "who is hiring",
                "hitsPerPage": 3,
            },
            timeout=10,
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        # Find the official whoishiring post
        thread_id = None
        for hit in hits:
            if hit.get("author") == "whoishiring" and "who is hiring" in (hit.get("title") or "").lower():
                thread_id = hit.get("objectID")
                break
        if not thread_id:
            # Fallback: just use latest hit
            thread_id = hits[0].get("objectID") if hits else None
        if not thread_id:
            return []

        # Fetch comments (job posts) searching for the role
        role_keywords = role.lower().split()[:3]
        for keyword in role_keywords:
            cresp = requests.get(
                f"{HN_API}/search",
                params={
                    "tags": f"comment,story_{thread_id}",
                    "query": keyword,
                    "hitsPerPage": max_results,
                },
                timeout=10,
            )
            if cresp.status_code != 200:
                continue
            for hit in cresp.json().get("hits", []):
                text = hit.get("comment_text") or hit.get("story_text") or ""
                # Strip HTML tags
                clean_text = re.sub(r"<[^>]+>", " ", text).strip()
                if not clean_text or len(clean_text) < 50:
                    continue

                # Country filter (loose) — only filter if specifically India
                if country == "IN":
                    has_india = bool(re.search(r"\b(india|bangalore|mumbai|delhi|hyderabad|pune|chennai|remote)\b", clean_text, re.I))
                    has_global = bool(re.search(r"\b(remote|worldwide|global|anywhere)\b", clean_text, re.I))
                    if not has_india and not has_global:
                        continue

                email = _extract_email(clean_text)
                url = _extract_url(clean_text)
                post_url = f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"

                # Extract company name (usually first | separated token)
                company = ""
                pipe_split = clean_text.split("|")
                if len(pipe_split) > 1:
                    company = pipe_split[0].strip()[:50]

                # Score: HN posts are generally high quality
                score = 60  # base score for HN
                if email: score += 20
                if url: score += 10
                if company: score += 10

                posts.append({
                    "poster_name": hit.get("author", ""),
                    "poster_email": email,
                    "poster_profile_url": f"https://news.ycombinator.com/user?id={hit.get('author', '')}",
                    "company": company,
                    "role_mentioned": role,
                    "post_text": clean_text[:800],
                    "post_url": post_url,
                    "source": "hn_hiring",
                    "country": country,
                    "legitimacy_score": min(score, 100),
                    "scraped_at": _now_iso(),
                })

            if len(posts) >= max_results:
                break

    except Exception as e:
        print(f"[hn_hiring] Error: {e}")

    # Dedupe by post_url
    seen = set()
    unique = []
    for p in posts:
        if p["post_url"] not in seen:
            seen.add(p["post_url"])
            unique.append(p)
    return unique[:max_results]
