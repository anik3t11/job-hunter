from __future__ import annotations
"""
Social hiring post scraper.
Sources:
  1. Google  → site:linkedin.com/posts  "hiring" "<role>"
  2. Reddit  → r/forhire, r/jobbit, r/hiring via public JSON API
  3. Nitter  → public Twitter mirrors for hiring tweets
"""
import re
import time
import hashlib
import requests
from datetime import datetime, timezone

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

# Nitter public mirrors (try in order)
NITTER_MIRRORS = [
    "https://nitter.net",
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
]

REDDIT_HIRING_SUBS = ["forhire", "jobbit", "hiring"]


# ── Helpers ────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _post_url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _extract_email(text: str) -> str:
    m = re.search(r"[\w.+\-]+@[\w\-]+\.[\w.]+", text or "")
    return m.group(0).lower() if m else ""


def _extract_role(text: str, query_role: str) -> str:
    """Try to pull the role name from post text; fallback to query."""
    # Look for "hiring a/an X", "looking for X", "we need a X"
    patterns = [
        r"hiring (?:a |an )?([A-Za-z ]{3,40}?)(?:\s*[-|!@\n]|$)",
        r"looking for (?:a |an )?([A-Za-z ]{3,40}?)(?:\s*[-|!@\n]|$)",
        r"open (?:role|position) (?:for )?(?:a |an )?([A-Za-z ]{3,40}?)(?:\s*[-|!@\n]|$)",
    ]
    for pat in patterns:
        m = re.search(pat, text or "", re.I)
        if m:
            candidate = m.group(1).strip()
            if 3 < len(candidate) < 40:
                return candidate
    return query_role


def _extract_company(text: str) -> str:
    m = re.search(r"(?:at|@)\s+([A-Za-z][A-Za-z0-9 &.,]{1,30}?)(?:\s*[-|!@\n]|$)", text or "")
    return m.group(1).strip() if m else ""


# ── Google → LinkedIn posts ────────────────────────────────────────────────

def scrape_linkedin_posts_via_google(role: str, country: str = "IN", max_results: int = 10) -> list:
    """
    Search Google for LinkedIn hiring posts matching the role.
    Uses DuckDuckGo HTML endpoint (no API key needed).
    """
    query = 'site:linkedin.com/posts "{}" hiring'.format(role)
    url = "https://html.duckduckgo.com/html/"
    posts = []
    try:
        resp = requests.post(
            url,
            data={"q": query, "b": "", "kl": ""},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        # Parse result links and snippets
        link_pattern = re.findall(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            resp.text, re.S
        )
        snippet_pattern = re.findall(
            r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
            resp.text, re.S
        )
        for i, (href, title) in enumerate(link_pattern[:max_results]):
            # DDG wraps in redirect — extract real URL
            real_url = href
            uddg_match = re.search(r"uddg=([^&]+)", href)
            if uddg_match:
                from urllib.parse import unquote
                real_url = unquote(uddg_match.group(1))

            if "linkedin.com" not in real_url:
                continue

            snippet = snippet_pattern[i] if i < len(snippet_pattern) else ""
            snippet_clean = re.sub(r"<[^>]+>", "", snippet).strip()
            title_clean = re.sub(r"<[^>]+>", "", title).strip()
            post_text = "{} {}".format(title_clean, snippet_clean)

            posts.append({
                "poster_name": "",
                "poster_email": _extract_email(post_text),
                "poster_profile_url": real_url,
                "company": _extract_company(post_text),
                "role_mentioned": _extract_role(post_text, role),
                "post_text": post_text[:800],
                "post_url": real_url,
                "source": "linkedin_post",
                "country": country,
                "scraped_at": _now_iso(),
            })
    except Exception as e:
        print("[social] LinkedIn/Google scrape error:", e)

    return posts


# ── Reddit ─────────────────────────────────────────────────────────────────

def scrape_reddit(role: str, country: str = "IN", max_results: int = 15) -> list:
    """
    Search Reddit's public JSON API for hiring posts mentioning the role.
    No auth needed — uses public /search.json endpoint.
    """
    posts = []
    seen = set()

    for sub in REDDIT_HIRING_SUBS:
        url = "https://www.reddit.com/r/{}/search.json".format(sub)
        params = {
            "q": role,
            "restrict_sr": "1",
            "sort": "new",
            "limit": 10,
            "t": "month",
        }
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            if resp.status_code == 429:
                time.sleep(2)
                resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            children = data.get("data", {}).get("children", [])

            for child in children:
                d = child.get("data", {})
                post_url = "https://www.reddit.com{}".format(d.get("permalink", ""))
                if post_url in seen:
                    continue
                seen.add(post_url)

                title = d.get("title", "")
                selftext = d.get("selftext", "")[:600]
                post_text = "{} {}".format(title, selftext)

                # Skip "[FOR HIRE]" posts — we want "[HIRING]"
                if re.search(r"\[for hire\]", title, re.I):
                    continue

                posts.append({
                    "poster_name": d.get("author", ""),
                    "poster_email": _extract_email(post_text),
                    "poster_profile_url": "https://reddit.com/u/{}".format(d.get("author", "")),
                    "company": _extract_company(post_text),
                    "role_mentioned": _extract_role(post_text, role),
                    "post_text": post_text[:800],
                    "post_url": post_url,
                    "source": "reddit",
                    "country": country,
                    "scraped_at": _now_iso(),
                })

                if len(posts) >= max_results:
                    break

            time.sleep(0.5)  # Reddit rate limit courtesy

        except Exception as e:
            print("[social] Reddit scrape error (r/{}):".format(sub), e)

    return posts[:max_results]


# ── Nitter / Twitter ───────────────────────────────────────────────────────

def scrape_nitter(role: str, country: str = "IN", max_results: int = 10) -> list:
    """
    Search Nitter (public Twitter mirror) for hiring tweets.
    Tries each mirror in order until one responds.
    """
    posts = []
    query = "{} hiring".format(role)

    for mirror in NITTER_MIRRORS:
        try:
            url = "{}/search".format(mirror)
            resp = requests.get(
                url,
                params={"q": query, "f": "tweets"},
                headers=HEADERS,
                timeout=12,
            )
            if resp.status_code != 200:
                continue

            # Parse tweet cards from HTML
            tweet_blocks = re.findall(
                r'<div class="tweet-content[^"]*">(.*?)</div>',
                resp.text, re.S
            )
            profile_links = re.findall(
                r'<a class="username"[^>]+href="(/[^"]+)"[^>]*>([^<]+)</a>',
                resp.text, re.S
            )
            tweet_links = re.findall(
                r'<a class="tweet-link"[^>]+href="(/[^"]+)"',
                resp.text, re.S
            )

            for i, block in enumerate(tweet_blocks[:max_results]):
                text = re.sub(r"<[^>]+>", "", block).strip()
                if not text:
                    continue

                handle = profile_links[i][0].strip("/") if i < len(profile_links) else ""
                display_name = profile_links[i][1].strip() if i < len(profile_links) else ""
                tweet_path = tweet_links[i] if i < len(tweet_links) else ""
                tweet_url = "{}{}".format(mirror, tweet_path) if tweet_path else mirror

                posts.append({
                    "poster_name": display_name,
                    "poster_email": _extract_email(text),
                    "poster_profile_url": "https://twitter.com/{}".format(handle) if handle else "",
                    "company": _extract_company(text),
                    "role_mentioned": _extract_role(text, role),
                    "post_text": text[:800],
                    "post_url": tweet_url,
                    "source": "twitter",
                    "country": country,
                    "scraped_at": _now_iso(),
                })

            if posts:
                break  # Got results from this mirror — stop trying

        except Exception as e:
            print("[social] Nitter scrape error ({}):".format(mirror), e)
            continue

    return posts[:max_results]


# ── Main entry point ───────────────────────────────────────────────────────

def scrape_social(role: str, country: str = "IN", sources: list = None) -> list:
    """
    Scrape hiring posts from social platforms.
    sources: list of 'linkedin_post', 'reddit', 'twitter' (default: all)
    Returns list of post dicts ready for insert_social_posts().
    """
    if sources is None:
        sources = ["linkedin_post", "reddit", "twitter"]

    all_posts = []
    seen_urls = set()

    if "linkedin_post" in sources:
        for post in scrape_linkedin_posts_via_google(role, country):
            if post["post_url"] not in seen_urls:
                seen_urls.add(post["post_url"])
                all_posts.append(post)

    if "reddit" in sources:
        for post in scrape_reddit(role, country):
            if post["post_url"] not in seen_urls:
                seen_urls.add(post["post_url"])
                all_posts.append(post)

    if "twitter" in sources:
        for post in scrape_nitter(role, country):
            if post["post_url"] not in seen_urls:
                seen_urls.add(post["post_url"])
                all_posts.append(post)

    return all_posts
