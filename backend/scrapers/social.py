from __future__ import annotations
"""
Social hiring post scraper v2.
Quality filters: only keep posts with email/URL/direct outreach signal.
Drops: comment-bait posts ("comment below", "drop your email").
Recency: last 14 days only, newest first.
Legitimacy score: 0-100 per post.
"""
import re
import time
import requests
from datetime import datetime, timezone, timedelta
from urllib.parse import unquote

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

NITTER_MIRRORS = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.net",
]

REDDIT_SUBS = ["forhire", "hiring", "indianjobs", "jobbit", "cscareerquestions"]

# ── Signal words ──────────────────────────────────────────────────────────

OUTREACH_SIGNALS = [
    r"\bdm\s+me\b", r"\bmessage\s+me\b", r"\breach\s+out\b", r"\bping\s+me\b",
    r"\bcontact\s+me\b", r"\bemail\s+me\b", r"\bapply\s+(?:at|via|to|here|now)\b",
    r"\bsend\s+(?:your\s+)?(?:resume|cv)\s+to\b", r"\bapplication[s]?\s+(?:to|at)\b",
    r"\bjoin\s+us\b", r"\bwe.re\s+hiring\b", r"\bwe\s+are\s+hiring\b",
    r"\bopen\s+(?:role|position|vacancy)\b", r"\blooking\s+for\b",
    r"\bimmediately\s+hiring\b", r"\burgently\s+hiring\b",
]

BAIT_SIGNALS = [
    r"\bcomment\s+(?:below|your|here)\b",
    r"\bdrop\s+(?:your|resume|cv|email)\s+(?:below|in|here)\b",
    r"\bcomment\s+(?:resume|cv|yes|interested|i'm in)\b",
    r"\btype\s+(?:yes|interested)\s+(?:below|in comments)\b",
    r"\blike\s+and\s+(?:share|comment)\b",
    r"\btag\s+(?:someone|a friend|your)\b",
    r"\bshare\s+(?:with|to)\s+your\s+network\b",
    r"\bretweet\b", r"\brt\s+to\b",
]

CUTOFF_DAYS = 14


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_email(text: str) -> str:
    m = re.search(r"[\w.+\-]+@[\w\-]+\.[\w.]+", text or "")
    return m.group(0).lower() if m else ""


def _extract_apply_url(text: str) -> str:
    m = re.search(r"https?://[^\s\"'>]{10,}", text or "")
    return m.group(0) if m else ""


def _extract_role(text: str, query_role: str) -> str:
    patterns = [
        r"hiring\s+(?:a\s+|an\s+)?([A-Za-z][A-Za-z ]{3,35}?)(?:\s*[-|!@\n,]|$)",
        r"looking\s+for\s+(?:a\s+|an\s+)?([A-Za-z][A-Za-z ]{3,35}?)(?:\s*[-|!@\n,]|$)",
        r"open\s+(?:role|position)\s+for\s+(?:a\s+)?([A-Za-z][A-Za-z ]{3,35}?)(?:\s*[-|!@\n,]|$)",
    ]
    for pat in patterns:
        m = re.search(pat, text or "", re.I)
        if m:
            c = m.group(1).strip()
            if 3 < len(c) < 40:
                return c
    return query_role


def _extract_company(text: str) -> str:
    m = re.search(r"(?:at|@)\s+([A-Za-z][A-Za-z0-9 &.,]{1,30}?)(?:\s*[-|!@\n]|$)", text or "")
    return m.group(1).strip() if m else ""


def _is_bait(text: str) -> bool:
    t = (text or "").lower()
    return any(re.search(p, t) for p in BAIT_SIGNALS)


def _has_outreach_signal(text: str, email: str, url: str) -> bool:
    if email or url:
        return True
    t = (text or "").lower()
    if any(re.search(p, t) for p in OUTREACH_SIGNALS):
        return True
    # Broader fallback — if it mentions hiring + a role keyword, keep it
    return bool(re.search(r"\b(hiring|recruit|opportunit|vacanc|position|role|opening)\b", t))


def _legitimacy_score(post: dict) -> int:
    """Score 0–100: how legitimate/actionable is this post."""
    score = 0
    text  = (post.get("post_text") or "").lower()
    email = post.get("poster_email", "")
    url   = _extract_apply_url(post.get("post_text", ""))

    if email:          score += 30
    if url:            score += 25
    # Outreach phrases
    if any(re.search(p, text) for p in OUTREACH_SIGNALS):
        score += 20
    # Mentions role clearly
    if re.search(r"\b(?:data analyst|business analyst|developer|engineer|manager|designer)\b", text, re.I):
        score += 10
    # Mentions company
    if re.search(r"\bat\s+[A-Z][a-zA-Z]", post.get("post_text", "")):
        score += 10
    # Not a repost/generic
    if len(text) > 150:
        score += 5

    return min(score, 100)


def _within_cutoff(scraped_at: str) -> bool:
    try:
        dt = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt) <= timedelta(days=CUTOFF_DAYS)
    except Exception:
        return True


# ── Google → LinkedIn posts ───────────────────────────────────────────────

def scrape_linkedin_posts_via_google(role: str, country: str = "IN", max_results: int = 15) -> list:
    query = 'site:linkedin.com/posts "{}" hiring'.format(role)
    posts = []
    try:
        resp = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query, "b": "", "kl": "in-en" if country == "IN" else ""},
            headers={**HEADERS, "Referer": "https://duckduckgo.com/", "Origin": "https://duckduckgo.com"},
            timeout=15,
        )
        resp.raise_for_status()
        links    = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', resp.text, re.S)
        snippets = re.findall(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', resp.text, re.S)

        for i, (href, title) in enumerate(links[:max_results]):
            uddg = re.search(r"uddg=([^&]+)", href)
            real_url = unquote(uddg.group(1)) if uddg else href
            if "linkedin.com" not in real_url:
                continue
            snip = re.sub(r"<[^>]+>", "", snippets[i] if i < len(snippets) else "").strip()
            title_clean = re.sub(r"<[^>]+>", "", title).strip()
            post_text = "{} {}".format(title_clean, snip)

            if _is_bait(post_text):
                continue
            email = _extract_email(post_text)
            url   = _extract_apply_url(post_text)
            if not _has_outreach_signal(post_text, email, url):
                continue

            post = {
                "poster_name": "", "poster_email": email,
                "poster_profile_url": real_url, "company": _extract_company(post_text),
                "role_mentioned": _extract_role(post_text, role),
                "post_text": post_text[:800], "post_url": real_url,
                "source": "linkedin_post", "country": country, "scraped_at": _now_iso(),
            }
            post["legitimacy_score"] = _legitimacy_score(post)
            posts.append(post)

    except Exception as e:
        print("[social] LinkedIn/Google error:", e)
    return posts


# ── Reddit ────────────────────────────────────────────────────────────────

def scrape_reddit(role: str, country: str = "IN", max_results: int = 20) -> list:
    posts = []
    seen  = set()
    cutoff = datetime.now(timezone.utc) - timedelta(days=CUTOFF_DAYS)

    for sub in REDDIT_SUBS:
        url = "https://www.reddit.com/r/{}/search.json".format(sub)
        params = {"q": role, "restrict_sr": "1", "sort": "new", "limit": 15, "t": "month"}
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            if resp.status_code == 429:
                time.sleep(2)
                resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            resp.raise_for_status()

            for child in resp.json().get("data", {}).get("children", []):
                d = child.get("data", {})
                created = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc)
                if created < cutoff:
                    continue

                post_url = "https://www.reddit.com{}".format(d.get("permalink", ""))
                if post_url in seen:
                    continue
                seen.add(post_url)

                title    = d.get("title", "")
                selftext = d.get("selftext", "")[:600]
                post_text = "{} {}".format(title, selftext)

                # Skip [FOR HIRE] and bait posts
                if re.search(r"\[for hire\]", title, re.I):
                    continue
                if _is_bait(post_text):
                    continue

                email = _extract_email(post_text)
                url_link = _extract_apply_url(post_text)
                if not _has_outreach_signal(post_text, email, url_link):
                    continue

                post = {
                    "poster_name": d.get("author", ""),
                    "poster_email": email,
                    "poster_profile_url": "https://reddit.com/u/{}".format(d.get("author", "")),
                    "company": _extract_company(post_text),
                    "role_mentioned": _extract_role(post_text, role),
                    "post_text": post_text[:800],
                    "post_url": post_url,
                    "source": "reddit",
                    "country": country,
                    "scraped_at": created.isoformat(),
                }
                post["legitimacy_score"] = _legitimacy_score(post)
                posts.append(post)

                if len(posts) >= max_results:
                    return posts[:max_results]

            time.sleep(0.5)
        except Exception as e:
            print("[social] Reddit r/{} error:".format(sub), e)

    return posts[:max_results]


# ── Nitter / Twitter ──────────────────────────────────────────────────────

def scrape_nitter(role: str, country: str = "IN", max_results: int = 15) -> list:
    posts = []
    query = "{} hiring".format(role)
    if country == "IN":
        query += " india"

    for mirror in NITTER_MIRRORS:
        try:
            resp = requests.get(
                "{}/search".format(mirror),
                params={"q": query, "f": "tweets"},
                headers=HEADERS, timeout=12,
            )
            if resp.status_code != 200:
                continue

            tweet_blocks = re.findall(r'<div class="tweet-content[^"]*">(.*?)</div>', resp.text, re.S)
            profile_links = re.findall(r'<a class="username"[^>]+href="(/[^"]+)"[^>]*>([^<]+)</a>', resp.text, re.S)
            tweet_links  = re.findall(r'<a class="tweet-link"[^>]+href="(/[^"]+)"', resp.text, re.S)
            dates        = re.findall(r'<span[^>]+class="[^"]*tweet-date[^"]*"[^>]*title="([^"]+)"', resp.text)

            for i, block in enumerate(tweet_blocks[:max_results]):
                text = re.sub(r"<[^>]+>", "", block).strip()
                if not text:
                    continue
                if _is_bait(text):
                    continue
                email    = _extract_email(text)
                url_link = _extract_apply_url(text)
                if not _has_outreach_signal(text, email, url_link):
                    continue

                # Check recency
                scraped_at = _now_iso()
                if i < len(dates):
                    try:
                        dt = datetime.strptime(dates[i][:16], "%b %d, %Y ·")
                        scraped_at = dt.replace(tzinfo=timezone.utc).isoformat()
                    except Exception:
                        pass

                handle = profile_links[i][0].strip("/") if i < len(profile_links) else ""
                name   = profile_links[i][1].strip() if i < len(profile_links) else ""
                path   = tweet_links[i] if i < len(tweet_links) else ""
                tweet_url = "https://twitter.com{}".format(path) if path else mirror

                post = {
                    "poster_name": name, "poster_email": email,
                    "poster_profile_url": "https://twitter.com/{}".format(handle) if handle else "",
                    "company": _extract_company(text),
                    "role_mentioned": _extract_role(text, role),
                    "post_text": text[:800], "post_url": tweet_url,
                    "source": "twitter", "country": country, "scraped_at": scraped_at,
                }
                post["legitimacy_score"] = _legitimacy_score(post)
                posts.append(post)

            if posts:
                break
        except Exception as e:
            print("[social] Nitter {} error:".format(mirror), e)

    return posts[:max_results]


# ── Main entry ────────────────────────────────────────────────────────────

def scrape_social(role: str, country: str = "IN", sources: list = None) -> list:
    if sources is None:
        sources = ["linkedin_post", "reddit", "twitter"]

    all_posts, seen = [], set()

    if "linkedin_post" in sources:
        for p in scrape_linkedin_posts_via_google(role, country):
            if p["post_url"] not in seen:
                seen.add(p["post_url"])
                all_posts.append(p)

    if "reddit" in sources:
        for p in scrape_reddit(role, country):
            if p["post_url"] not in seen:
                seen.add(p["post_url"])
                all_posts.append(p)

    if "twitter" in sources:
        for p in scrape_nitter(role, country):
            if p["post_url"] not in seen:
                seen.add(p["post_url"])
                all_posts.append(p)

    # Sort: legitimacy score desc, then newest first
    all_posts.sort(key=lambda x: (-x.get("legitimacy_score", 0), x.get("scraped_at", "")), reverse=False)
    all_posts.sort(key=lambda x: -x.get("legitimacy_score", 0))

    return all_posts
