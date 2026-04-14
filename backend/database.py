from __future__ import annotations
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "jobs.db"


def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    # Step 1: create tables (without new-column indexes — those come after migration)
    c.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            title               TEXT NOT NULL,
            company             TEXT NOT NULL,
            location            TEXT,
            salary_raw          TEXT,
            salary_min          INTEGER,
            salary_max          INTEGER,
            experience_required TEXT,
            experience_min      REAL,
            experience_max      REAL,
            description         TEXT,
            skills_required     TEXT,
            job_url             TEXT NOT NULL,
            recruiter_email     TEXT,
            source              TEXT NOT NULL,
            status              TEXT NOT NULL DEFAULT 'new',
            match_score         INTEGER DEFAULT 0,
            match_breakdown     TEXT DEFAULT '{}',
            notes               TEXT DEFAULT '',
            scraped_at          TEXT NOT NULL,
            applied_at          TEXT,
            url_hash            TEXT UNIQUE NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_status   ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_jobs_source   ON jobs(source);
        CREATE INDEX IF NOT EXISTS idx_jobs_score    ON jobs(match_score DESC);
        CREATE INDEX IF NOT EXISTS idx_jobs_url_hash ON jobs(url_hash);

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS social_posts (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            poster_name         TEXT,
            poster_email        TEXT,
            poster_profile_url  TEXT,
            company             TEXT,
            role_mentioned      TEXT,
            post_text           TEXT,
            post_url            TEXT UNIQUE NOT NULL,
            source              TEXT NOT NULL,
            country             TEXT DEFAULT 'IN',
            scraped_at          TEXT NOT NULL,
            status              TEXT NOT NULL DEFAULT 'new'
        );

        CREATE INDEX IF NOT EXISTS idx_social_source  ON social_posts(source);
        CREATE INDEX IF NOT EXISTS idx_social_country ON social_posts(country);
        CREATE INDEX IF NOT EXISTS idx_social_status  ON social_posts(status);

        INSERT OR IGNORE INTO settings (key, value) VALUES
            ('gmail_address', ''),
            ('gmail_app_password', ''),
            ('user_name', ''),
            ('user_skills', ''),
            ('user_experience_years', '0'),
            ('user_preferred_locations', ''),
            ('user_salary_target', '0'),
            ('user_salary_min', '0'),
            ('resume_summary', ''),
            ('notice_period', ''),
            ('resume_text', ''),
            ('last_search_role', ''),
            ('last_search_country', 'IN'),
            ('last_search_locations', ''),
            ('db_version', '3');
    """)

    # Step 2: migrate — add columns that didn't exist in v1
    existing = {row[1] for row in c.execute("PRAGMA table_info(jobs)").fetchall()}
    migrations = {
        "country":          "ALTER TABLE jobs ADD COLUMN country TEXT DEFAULT 'IN'",
        "salary_target":    "ALTER TABLE jobs ADD COLUMN salary_target INTEGER",
        "skills_gap":       "ALTER TABLE jobs ADD COLUMN skills_gap TEXT",
        "is_hot":           "ALTER TABLE jobs ADD COLUMN is_hot INTEGER DEFAULT 0",
        "followup_1_at":    "ALTER TABLE jobs ADD COLUMN followup_1_at TEXT",
        "followup_2_at":    "ALTER TABLE jobs ADD COLUMN followup_2_at TEXT",
        "followup_due_at":  "ALTER TABLE jobs ADD COLUMN followup_due_at TEXT",
        "is_stretch":       "ALTER TABLE jobs ADD COLUMN is_stretch INTEGER DEFAULT 0",
        "skills_stretch":   "ALTER TABLE jobs ADD COLUMN skills_stretch TEXT",
        "role_variant":     "ALTER TABLE jobs ADD COLUMN role_variant TEXT",
    }
    for col, sql in migrations.items():
        if col not in existing:
            c.execute(sql)

    # Step 3: create indexes that depend on migrated columns
    c.executescript("""
        CREATE INDEX IF NOT EXISTS idx_jobs_followup ON jobs(followup_due_at);
        CREATE INDEX IF NOT EXISTS idx_jobs_country  ON jobs(country);
    """)

    conn.commit()
    conn.close()


def get_settings() -> dict:
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def save_settings(updates: dict):
    conn = get_connection()
    for key, value in updates.items():
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )
    conn.commit()
    conn.close()


def insert_jobs(jobs: list) -> tuple:
    conn = get_connection()
    inserted = 0
    skipped = 0
    for job in jobs:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO jobs
                   (title, company, location, country, salary_raw, salary_min, salary_max,
                    salary_target, experience_required, experience_min, experience_max,
                    description, skills_required, skills_gap, job_url, recruiter_email,
                    source, match_score, match_breakdown, is_hot, scraped_at,
                    followup_due_at, url_hash)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    job["title"], job["company"], job.get("location", ""),
                    job.get("country", "IN"),
                    job.get("salary_raw", ""), job.get("salary_min"),
                    job.get("salary_max"), job.get("salary_target"),
                    job.get("experience_required", ""),
                    job.get("experience_min"), job.get("experience_max"),
                    job.get("description", ""), job.get("skills_required", ""),
                    job.get("skills_gap", ""),
                    job["job_url"], job.get("recruiter_email"),
                    job["source"], job.get("match_score", 0),
                    job.get("match_breakdown", "{}"),
                    job.get("is_hot", 0),
                    job["scraped_at"],
                    job.get("followup_due_at"),
                    job["url_hash"],
                ),
            )
            if conn.execute("SELECT changes()").fetchone()[0] > 0:
                inserted += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1
    conn.commit()
    conn.close()
    return inserted, skipped


def get_jobs(
    status=None,
    source=None,
    min_score=None,
    country=None,
    followup_due=False,
    page: int = 1,
    per_page: int = 20,
    sort: str = "score",
) -> tuple:
    conn = get_connection()
    conditions = []
    params = []
    if status and status != "all":
        conditions.append("status = ?")
        params.append(status)
    if source and source != "all":
        conditions.append("source = ?")
        params.append(source)
    if min_score is not None:
        conditions.append("match_score >= ?")
        params.append(min_score)
    if country and country != "all":
        conditions.append("country = ?")
        params.append(country)
    if followup_due:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        conditions.append("status = 'applied' AND followup_due_at IS NOT NULL AND followup_due_at <= ?")
        params.append(now)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    order_map = {
        "score": "match_score DESC",
        "date": "scraped_at DESC",
        "hot": "is_hot DESC, scraped_at DESC",
    }
    order = order_map.get(sort, "match_score DESC")
    offset = (page - 1) * per_page

    total = conn.execute(
        "SELECT COUNT(*) FROM jobs {}".format(where), params
    ).fetchone()[0]

    rows = conn.execute(
        """SELECT id, title, company, location, country, salary_raw, salary_min,
                   salary_max, salary_target, experience_required, experience_min,
                   experience_max, skills_required, skills_gap, job_url, recruiter_email,
                   source, status, match_score, match_breakdown, notes, is_hot,
                   scraped_at, applied_at, followup_1_at, followup_2_at, followup_due_at,
                   substr(description, 1, 300) AS description_snippet
            FROM jobs {where}
            ORDER BY {order}
            LIMIT ? OFFSET ?""".format(where=where, order=order),
        params + [per_page, offset],
    ).fetchall()

    conn.close()
    return [dict(r) for r in rows], total


def get_job_detail(job_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_job(job_id: int, updates: dict):
    conn = get_connection()
    fields = ", ".join("{} = ?".format(k) for k in updates)
    values = list(updates.values()) + [job_id]
    conn.execute("UPDATE jobs SET {} WHERE id = ?".format(fields), values)
    conn.commit()
    conn.close()


def get_stats() -> dict:
    conn = get_connection()
    by_status = {
        r["status"]: r["cnt"]
        for r in conn.execute(
            "SELECT status, COUNT(*) AS cnt FROM jobs GROUP BY status"
        ).fetchall()
    }
    by_source = {
        r["source"]: r["cnt"]
        for r in conn.execute(
            "SELECT source, COUNT(*) AS cnt FROM jobs GROUP BY source"
        ).fetchall()
    }
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    followup_due = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE status='applied' AND followup_due_at IS NOT NULL AND followup_due_at <= ?",
        (now,)
    ).fetchone()[0]
    avg_row = conn.execute("SELECT AVG(match_score) AS avg FROM jobs").fetchone()
    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    conn.close()
    return {
        "total_jobs": total,
        "by_status": by_status,
        "by_source": by_source,
        "avg_match_score": round(avg_row["avg"] or 0),
        "followup_due": followup_due,
    }


def get_followup_due() -> list:
    conn = get_connection()
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    rows = conn.execute(
        """SELECT id, title, company, recruiter_email, applied_at,
                  followup_1_at, followup_2_at, followup_due_at
           FROM jobs
           WHERE status='applied' AND followup_due_at IS NOT NULL AND followup_due_at <= ?
           ORDER BY followup_due_at ASC""",
        (now,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def export_jobs_csv() -> str:
    import csv, io
    conn = get_connection()
    rows = conn.execute(
        """SELECT title, company, location, country, salary_raw, experience_required,
                  source, status, match_score, job_url, recruiter_email,
                  scraped_at, applied_at, followup_1_at, followup_2_at, notes
           FROM jobs ORDER BY match_score DESC"""
    ).fetchall()
    conn.close()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "Title", "Company", "Location", "Country", "Salary", "Experience",
        "Source", "Status", "Match Score", "Job URL", "Recruiter Email",
        "Scraped At", "Applied At", "Followup 1", "Followup 2", "Notes"
    ])
    for row in rows:
        writer.writerow(list(row))
    return out.getvalue()


def clear_jobs():
    conn = get_connection()
    conn.execute("DELETE FROM jobs")
    conn.commit()
    conn.close()


def insert_social_posts(posts: list) -> tuple:
    conn = get_connection()
    inserted = 0
    skipped = 0
    for post in posts:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO social_posts
                   (poster_name, poster_email, poster_profile_url, company, role_mentioned,
                    post_text, post_url, source, country, scraped_at, status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    post.get("poster_name", ""),
                    post.get("poster_email", ""),
                    post.get("poster_profile_url", ""),
                    post.get("company", ""),
                    post.get("role_mentioned", ""),
                    post.get("post_text", ""),
                    post["post_url"],
                    post["source"],
                    post.get("country", "IN"),
                    post["scraped_at"],
                    post.get("status", "new"),
                ),
            )
            if conn.execute("SELECT changes()").fetchone()[0] > 0:
                inserted += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1
    conn.commit()
    conn.close()
    return inserted, skipped


def get_social_posts(country=None, source=None, status=None, page: int = 1, per_page: int = 20) -> tuple:
    conn = get_connection()
    conditions = []
    params = []
    if country and country != "all":
        conditions.append("country = ?")
        params.append(country)
    if source and source != "all":
        conditions.append("source = ?")
        params.append(source)
    if status and status != "all":
        conditions.append("status = ?")
        params.append(status)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    offset = (page - 1) * per_page

    total = conn.execute("SELECT COUNT(*) FROM social_posts {}".format(where), params).fetchone()[0]
    rows = conn.execute(
        """SELECT * FROM social_posts {where}
           ORDER BY scraped_at DESC
           LIMIT ? OFFSET ?""".format(where=where),
        params + [per_page, offset],
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows], total


def update_social_post(post_id: int, updates: dict):
    conn = get_connection()
    fields = ", ".join("{} = ?".format(k) for k in updates)
    values = list(updates.values()) + [post_id]
    conn.execute("UPDATE social_posts SET {} WHERE id = ?".format(fields), values)
    conn.commit()
    conn.close()
