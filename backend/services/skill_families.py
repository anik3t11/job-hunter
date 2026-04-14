from __future__ import annotations
"""
Skill family definitions for fuzzy/transferable skill matching.
If a user knows ANY skill in a family they get partial credit for ALL others.
This ensures jobs aren't missed because of exact-keyword mismatch.
"""

# Each family: canonical_name → list of skills in the family
# Order within list doesn't matter — all are peers
SKILL_FAMILIES: dict = {
    "data_viz": [
        "tableau", "power bi", "powerbi", "looker", "looker studio", "google data studio",
        "metabase", "superset", "apache superset", "qlikview", "qlik sense", "sisense",
        "matplotlib", "seaborn", "plotly", "bokeh", "d3", "d3.js", "grafana",
        "data visualization", "data viz", "dashboarding", "reporting",
    ],
    "sql_databases": [
        "sql", "mysql", "postgresql", "postgres", "sqlite", "sql server", "mssql",
        "oracle", "oracle db", "db2", "teradata", "hive", "impala", "presto", "trino",
        "snowflake", "redshift", "amazon redshift", "bigquery", "google bigquery",
        "azure sql", "synapse", "aurora", "cockroachdb", "database",
    ],
    "nosql_databases": [
        "mongodb", "cassandra", "dynamodb", "redis", "elasticsearch", "couchdb",
        "firebase", "hbase", "neo4j", "graph database", "nosql",
    ],
    "python_ecosystem": [
        "python", "pandas", "numpy", "scipy", "scikit-learn", "sklearn",
        "jupyter", "ipython", "pyspark", "polars", "dask",
    ],
    "ml_ai": [
        "machine learning", "deep learning", "nlp", "natural language processing",
        "tensorflow", "pytorch", "keras", "xgboost", "lightgbm", "catboost",
        "hugging face", "transformers", "computer vision", "cv", "ai", "artificial intelligence",
        "neural network", "regression", "classification", "clustering", "random forest",
    ],
    "cloud_platforms": [
        "aws", "amazon web services", "gcp", "google cloud", "azure", "microsoft azure",
        "cloud", "s3", "ec2", "lambda", "cloud functions", "cloud storage",
        "databricks", "emr", "glue", "athena",
    ],
    "etl_pipelines": [
        "etl", "elt", "airflow", "apache airflow", "dbt", "data build tool",
        "informatica", "talend", "ssis", "pentaho", "fivetran", "stitch",
        "kafka", "apache kafka", "spark", "apache spark", "flink", "data pipeline",
        "data warehouse", "dwh", "data lake", "data lakehouse",
    ],
    "statistics_analytics": [
        "statistics", "statistical analysis", "probability", "hypothesis testing",
        "a/b testing", "ab testing", "experimentation", "regression analysis",
        "time series", "forecasting", "predictive analytics", "descriptive analytics",
        "business intelligence", "bi", "kpi", "metrics", "data analysis",
        "r", "rstudio", "spss", "sas", "stata",
    ],
    "spreadsheets": [
        "excel", "microsoft excel", "google sheets", "google spreadsheets",
        "pivot tables", "vlookup", "advanced excel", "vba", "macros",
    ],
    "programming": [
        "java", "scala", "go", "golang", "c++", "c#", "javascript", "typescript",
        "node.js", "react", "angular", "vue", "html", "css", "bash", "shell scripting",
        "ruby", "php", "swift", "kotlin",
    ],
    "project_tools": [
        "jira", "confluence", "trello", "asana", "monday.com", "notion",
        "slack", "teams", "git", "github", "gitlab", "bitbucket", "agile",
        "scrum", "kanban", "product management",
    ],
}

# Reverse lookup: skill_name → family_name
SKILL_TO_FAMILY: dict = {}
for _family, _skills in SKILL_FAMILIES.items():
    for _skill in _skills:
        SKILL_TO_FAMILY[_skill.lower()] = _family


def get_family(skill: str) -> str | None:
    """Return the family name for a skill, or None if not categorised."""
    return SKILL_TO_FAMILY.get(skill.lower().strip())


def get_family_members(skill: str) -> list:
    """Return all skills in the same family as the given skill."""
    family = get_family(skill)
    if not family:
        return []
    return SKILL_FAMILIES.get(family, [])


def user_skill_families(user_skills_str: str) -> set:
    """Return set of family names the user belongs to."""
    families = set()
    for skill in user_skills_str.lower().split(","):
        f = get_family(skill.strip())
        if f:
            families.add(f)
    return families


def skill_match_score(job_skill: str, user_skills_str: str) -> float:
    """
    Return 0.0–1.0 match score for a job skill against user's skill list.
    1.0 = exact match
    0.7 = same family (transferable)
    0.0 = no match
    """
    job_skill_lower = job_skill.lower().strip()
    user_lower = [s.strip().lower() for s in user_skills_str.split(",")]

    # Exact match
    if job_skill_lower in user_lower:
        return 1.0

    # Substring match (e.g. "power bi" vs "powerbi")
    for u in user_lower:
        if job_skill_lower in u or u in job_skill_lower:
            return 0.9

    # Same family (transferable skill)
    job_family = get_family(job_skill_lower)
    if job_family:
        for u in user_lower:
            if get_family(u) == job_family:
                return 0.7

    return 0.0


def compute_skills_gap_fuzzy(job: dict, user_skills_str: str) -> tuple:
    """
    Returns (gap_exact: list, gap_stretch: list).
    gap_exact   = skills in JD user definitely doesn't have
    gap_stretch = skills in JD user could transfer from a related skill
    """
    if not user_skills_str:
        return [], []

    import re
    jd_text = "{} {}".format(
        job.get("description", ""),
        job.get("skills_required", ""),
    ).lower()

    # Extract tech keywords from JD
    TECH_SKILLS = set()
    for skills in SKILL_FAMILIES.values():
        TECH_SKILLS.update(skills)

    found_in_jd = [s for s in TECH_SKILLS if s in jd_text]

    gap_exact = []
    gap_stretch = []

    for skill in found_in_jd:
        score = skill_match_score(skill, user_skills_str)
        if score >= 0.9:
            continue  # user has it
        elif score >= 0.6:
            gap_stretch.append(skill)  # transferable
        else:
            gap_exact.append(skill)

    # Dedupe and limit
    gap_exact   = sorted(set(gap_exact))[:6]
    gap_stretch = sorted(set(gap_stretch))[:6]
    return gap_exact, gap_stretch
