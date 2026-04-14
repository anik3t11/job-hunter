from __future__ import annotations
"""
Role cluster expansion.
When user searches "Data Analyst", also search for all related roles
so they never miss a relevant opportunity.
"""

# Each entry: canonical_role → list of variant roles to also search
ROLE_CLUSTERS: dict = {
    # Data / Analytics track
    "data analyst": [
        "data analyst", "business analyst", "senior data analyst",
        "senior business analyst", "product analyst", "bi analyst",
        "business intelligence analyst", "reporting analyst",
        "insights analyst", "analytics analyst", "mis analyst",
        "data analytics", "data specialist",
    ],
    "business analyst": [
        "business analyst", "data analyst", "product analyst",
        "senior business analyst", "systems analyst", "process analyst",
        "requirements analyst", "functional analyst",
    ],
    "data engineer": [
        "data engineer", "senior data engineer", "analytics engineer",
        "etl developer", "data pipeline engineer", "data infrastructure engineer",
        "big data engineer", "platform engineer", "data platform",
    ],
    "data scientist": [
        "data scientist", "senior data scientist", "ml engineer",
        "machine learning engineer", "ai engineer", "applied scientist",
        "research scientist", "quantitative analyst", "quant analyst",
        "modeling analyst",
    ],
    "product manager": [
        "product manager", "product owner", "senior product manager",
        "associate product manager", "apm", "technical product manager",
        "group product manager", "product lead",
    ],
    "software engineer": [
        "software engineer", "software developer", "backend engineer",
        "backend developer", "full stack engineer", "full stack developer",
        "frontend engineer", "senior software engineer", "sde", "sde2",
    ],
    "devops engineer": [
        "devops engineer", "sre", "site reliability engineer",
        "platform engineer", "cloud engineer", "infrastructure engineer",
        "mlops engineer",
    ],
    "ui ux designer": [
        "ui designer", "ux designer", "ui ux designer", "product designer",
        "visual designer", "interaction designer",
    ],
}

# Build reverse lookup: any variant → canonical
_VARIANT_TO_CANONICAL: dict = {}
for _canonical, _variants in ROLE_CLUSTERS.items():
    for _v in _variants:
        _VARIANT_TO_CANONICAL[_v.lower()] = _canonical


def expand_role(role: str, max_variants: int = 5) -> list:
    """
    Given a role string, return a list of related roles to search for.
    Includes the original role + up to max_variants related ones.
    Returns deduplicated list.
    """
    role_lower = role.lower().strip()

    # Direct match on canonical
    if role_lower in ROLE_CLUSTERS:
        variants = ROLE_CLUSTERS[role_lower]
        return _dedup([role] + variants)[:max_variants + 1]

    # Match via variant reverse lookup
    canonical = _VARIANT_TO_CANONICAL.get(role_lower)
    if canonical:
        variants = ROLE_CLUSTERS[canonical]
        return _dedup([role] + variants)[:max_variants + 1]

    # Fuzzy: partial match on canonical keys
    for canonical_key, variants in ROLE_CLUSTERS.items():
        if role_lower in canonical_key or canonical_key in role_lower:
            return _dedup([role] + variants)[:max_variants + 1]

    # No cluster found — return just the original role
    return [role]


def is_variant(role: str, search_role: str) -> bool:
    """True if 'role' is a variant of the searched 'search_role'."""
    role_lower = role.lower().strip()
    search_lower = search_role.lower().strip()
    return role_lower != search_lower and role_lower in [
        v.lower() for v in expand_role(search_role)
    ]


def _dedup(items: list) -> list:
    seen = set()
    result = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
