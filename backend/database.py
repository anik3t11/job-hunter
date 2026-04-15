from __future__ import annotations
"""
Database layer — auto-detects PostgreSQL (DATABASE_URL) or SQLite (local).
All public functions work identically regardless of backend.
"""
import os
import re
import sqlite3
from datetime import datetime, timezone

# ── Backend detection ──────────────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_PG       = bool(DATABASE_URL)
DB_PATH      = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "jobs.db"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════════════
# Unified connection wrapper
# ═══════════════════════════════════════════════════════════════════════════

class _Conn:
    """Thin wrapper that normalises SQLite and psycopg2 differences."""

    def __init__(self):
        if USE_PG:
            import psycopg2
            import psycopg2.extras
            url = DATABASE_URL
            # Railway sometimes gives postgres:// — psycopg2 needs postgresql://
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            self._pg   = psycopg2.connect(url)
            self._cur  = self._pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            self._sq   = None
        else:
            os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
            self._sq  = sqlite3.connect(DB_PATH)
            self._sq.row_factory = sqlite3.Row
            self._sq.execute("PRAGMA journal_mode=WAL")
            self._sq.execute("PRAGMA foreign_keys=ON")
            self._pg  = None
            self._cur = None

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _to_pg(sql: str) -> str:
        """Convert SQLite-style SQL to PostgreSQL."""
        sql = sql.replace("?", "%s")
        sql = re.sub(r"\bINSERT OR IGNORE\b", "INSERT", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bINSERT OR REPLACE\b", "INSERT", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bINTEGER PRIMARY KEY AUTOINCREMENT\b", "SERIAL PRIMARY KEY", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bdatetime\('now'\)", "NOW()", sql, flags=re.IGNORECASE)
        # ON CONFLICT(x,y) DO UPDATE SET → PostgreSQL already supports this syntax
        return sql

    def execute(self, sql: str, params=()):
        if USE_PG:
            pg_sql = self._to_pg(sql)
            # Append ON CONFLICT DO NOTHING for plain INSERT (after OR IGNORE replacement)
            if re.match(r"^\s*INSERT\b", pg_sql, re.IGNORECASE):
                if "on conflict" not in pg_sql.lower():
                    pg_sql = pg_sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
            self._cur.execute(pg_sql, params)
            return self
        else:
            self._sq_cur = self._sq.execute(sql, params)
            return self

    def executemany(self, sql: str, params_list):
        if USE_PG:
            pg_sql = self._to_pg(sql)
            import psycopg2.extras
            psycopg2.extras.execute_batch(self._cur, pg_sql, params_list)
        else:
            self._sq.executemany(sql, params_list)
        return self

    def executescript(self, script: str):
        """Run a multi-statement script."""
        if USE_PG:
            for stmt in script.split(";"):
                stmt = stmt.strip()
                if stmt:
                    self._cur.execute(self._to_pg(stmt))
        else:
            self._sq.executescript(script)
        return self

    def fetchone(self):
        if USE_PG:
            row = self._cur.fetchone()
            return dict(row) if row else None
        else:
            row = self._sq_cur.fetchone()
            return dict(row) if row else None

    def fetchall(self):
        if USE_PG:
            return [dict(r) for r in self._cur.fetchall()]
        else:
            return [dict(r) for r in self._sq_cur.fetchall()]

    @property
    def lastrowid(self):
        if USE_PG:
            self._cur.execute("SELECT lastval()")
            return self._cur.fetchone()["lastval"]
        else:
            return self._sq_cur.lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount if USE_PG else self._sq_cur.rowcount

    def commit(self):
        if USE_PG:
            self._pg.commit()
        else:
            self._sq.commit()

    def close(self):
        if USE_PG:
            self._cur.close()
            self._pg.close()
        else:
            self._sq.close()


def get_connection() -> _Conn:
    return _Conn()


# ═══════════════════════════════════════════════════════════════════════════
# INIT
# ═══════════════════════════════════════════════════════════════════════════

def init_db():
    conn = get_connection()

    if USE_PG:
        # PostgreSQL CREATE TABLE statements
        stmts = [
            """CREATE TABLE IF NOT EXISTS users (
                id            SERIAL PRIMARY KEY,
                email         TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                name          TEXT    DEFAULT '',
                is_admin      INTEGER DEFAULT 0,
                is_active     INTEGER DEFAULT 1,
                created_at    TEXT    NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS invite_whitelist (
                id        SERIAL PRIMARY KEY,
                email     TEXT UNIQUE NOT NULL,
                added_at  TEXT NOT NULL,
                used      INTEGER DEFAULT 0
            )""",
            """CREATE TABLE IF NOT EXISTS jobs (
                id                  SERIAL PRIMARY KEY,
                user_id             INTEGER NOT NULL DEFAULT 1,
                title               TEXT    NOT NULL,
                company             TEXT,
                location            TEXT,
                salary_min          INTEGER,
                salary_max          INTEGER,
                salary_raw          TEXT,
                salary_target       INTEGER,
                experience_required TEXT,
                description         TEXT,
                description_snippet TEXT,
                skills_required     TEXT,
                job_url             TEXT,
                url_hash            TEXT    UNIQUE,
                source              TEXT,
                country             TEXT    DEFAULT 'IN',
                recruiter_name      TEXT,
                recruiter_email     TEXT,
                status              TEXT    NOT NULL DEFAULT 'new',
                match_score         INTEGER DEFAULT 0,
                match_breakdown     TEXT,
                skills_gap          TEXT,
                skills_stretch      TEXT,
                is_hot              INTEGER DEFAULT 0,
                is_stretch          INTEGER DEFAULT 0,
                location_match      INTEGER DEFAULT 0,
                role_variant        TEXT,
                notes               TEXT,
                applied_at          TEXT,
                followup_1_at       TEXT,
                followup_2_at       TEXT,
                followup_due_at     TEXT,
                scraped_at          TEXT    NOT NULL DEFAULT NOW()
            )""",
            """CREATE TABLE IF NOT EXISTS settings (
                user_id  INTEGER NOT NULL,
                key      TEXT    NOT NULL,
                value    TEXT    NOT NULL DEFAULT '',
                PRIMARY KEY (user_id, key)
            )""",
            """CREATE TABLE IF NOT EXISTS social_posts (
                id                  SERIAL PRIMARY KEY,
                user_id             INTEGER NOT NULL DEFAULT 1,
                poster_name         TEXT,
                poster_email        TEXT,
                poster_profile_url  TEXT,
                company             TEXT,
                role_mentioned      TEXT,
                post_text           TEXT,
                post_url            TEXT    UNIQUE NOT NULL,
                source              TEXT    NOT NULL,
                country             TEXT    DEFAULT 'IN',
                legitimacy_score    INTEGER DEFAULT 0,
                scraped_at          TEXT    NOT NULL,
                status              TEXT    NOT NULL DEFAULT 'new'
            )""",
            """CREATE TABLE IF NOT EXISTS company_cache (
                id              SERIAL PRIMARY KEY,
                company_slug    TEXT    NOT NULL,
                role            TEXT    DEFAULT '',
                avg_salary_min  INTEGER,
                avg_salary_max  INTEGER,
                rating          REAL,
                review_count    INTEGER DEFAULT 0,
                review_summary  TEXT,
                source          TEXT    DEFAULT 'ambitionbox',
                cached_at       TEXT    NOT NULL,
                UNIQUE(company_slug, role)
            )""",
            "CREATE INDEX IF NOT EXISTS idx_jobs_user    ON jobs(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_jobs_status  ON jobs(status)",
            "CREATE INDEX IF NOT EXISTS idx_jobs_source  ON jobs(source)",
            "CREATE INDEX IF NOT EXISTS idx_jobs_country ON jobs(country)",
            "CREATE INDEX IF NOT EXISTS idx_jobs_score   ON jobs(match_score DESC)",
            "CREATE INDEX IF NOT EXISTS idx_jobs_hot     ON jobs(is_hot)",
            "CREATE INDEX IF NOT EXISTS idx_social_user  ON social_posts(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_social_src   ON social_posts(source)",
            "CREATE INDEX IF NOT EXISTS idx_social_score ON social_posts(legitimacy_score DESC)",
        ]
        for stmt in stmts:
            conn._cur.execute(stmt)
    else:
        # SQLite
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                name          TEXT    DEFAULT '',
                is_admin      INTEGER DEFAULT 0,
                is_active     INTEGER DEFAULT 1,
                created_at    TEXT    NOT NULL
            );
            CREATE TABLE IF NOT EXISTS invite_whitelist (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                email     TEXT UNIQUE NOT NULL,
                added_at  TEXT NOT NULL,
                used      INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS jobs (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id             INTEGER NOT NULL DEFAULT 1,
                title               TEXT    NOT NULL,
                company             TEXT,
                location            TEXT,
                salary_min          INTEGER,
                salary_max          INTEGER,
                salary_raw          TEXT,
                salary_target       INTEGER,
                experience_required TEXT,
                description         TEXT,
                description_snippet TEXT,
                skills_required     TEXT,
                job_url             TEXT,
                url_hash            TEXT    UNIQUE,
                source              TEXT,
                country             TEXT    DEFAULT 'IN',
                recruiter_name      TEXT,
                recruiter_email     TEXT,
                status              TEXT    NOT NULL DEFAULT 'new',
                match_score         INTEGER DEFAULT 0,
                match_breakdown     TEXT,
                skills_gap          TEXT,
                skills_stretch      TEXT,
                is_hot              INTEGER DEFAULT 0,
                is_stretch          INTEGER DEFAULT 0,
                location_match      INTEGER DEFAULT 0,
                role_variant        TEXT,
                notes               TEXT,
                applied_at          TEXT,
                followup_1_at       TEXT,
                followup_2_at       TEXT,
                followup_due_at     TEXT,
                scraped_at          TEXT    NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS settings (
                user_id  INTEGER NOT NULL,
                key      TEXT    NOT NULL,
                value    TEXT    NOT NULL DEFAULT '',
                PRIMARY KEY (user_id, key)
            );
            CREATE TABLE IF NOT EXISTS social_posts (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id             INTEGER NOT NULL DEFAULT 1,
                poster_name         TEXT,
                poster_email        TEXT,
                poster_profile_url  TEXT,
                company             TEXT,
                role_mentioned      TEXT,
                post_text           TEXT,
                post_url            TEXT    UNIQUE NOT NULL,
                source              TEXT    NOT NULL,
                country             TEXT    DEFAULT 'IN',
                legitimacy_score    INTEGER DEFAULT 0,
                scraped_at          TEXT    NOT NULL,
                status              TEXT    NOT NULL DEFAULT 'new'
            );
            CREATE TABLE IF NOT EXISTS company_cache (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                company_slug    TEXT    NOT NULL,
                role            TEXT    DEFAULT '',
                avg_salary_min  INTEGER,
                avg_salary_max  INTEGER,
                rating          REAL,
                review_count    INTEGER DEFAULT 0,
                review_summary  TEXT,
                source          TEXT    DEFAULT 'ambitionbox',
                cached_at       TEXT    NOT NULL,
                UNIQUE(company_slug, role)
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_user    ON jobs(user_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_status  ON jobs(status);
            CREATE INDEX IF NOT EXISTS idx_jobs_source  ON jobs(source);
            CREATE INDEX IF NOT EXISTS idx_jobs_country ON jobs(country);
            CREATE INDEX IF NOT EXISTS idx_jobs_score   ON jobs(match_score DESC);
            CREATE INDEX IF NOT EXISTS idx_jobs_hot     ON jobs(is_hot);
            CREATE INDEX IF NOT EXISTS idx_social_user  ON social_posts(user_id);
            CREATE INDEX IF NOT EXISTS idx_social_src   ON social_posts(source);
            CREATE INDEX IF NOT EXISTS idx_social_score ON social_posts(legitimacy_score DESC);
        """)

    # ── Column migrations (safe to run on every startup) ────────────────────
    _run_migrations(conn)

    # Seed admin whitelist from env
    admin_email = os.environ.get("ADMIN_EMAIL", "")
    if admin_email:
        conn.execute(
            "INSERT OR IGNORE INTO invite_whitelist (email, added_at) VALUES (?,?)",
            (admin_email.lower(), _now())
        )

    conn.commit()
    conn.close()


def _run_migrations(conn: "_Conn"):
    """Add columns that were introduced after initial schema deployment."""
    migrations = [
        # (table, column, definition)
        ("jobs", "location_match",  "INTEGER DEFAULT 0"),
        ("jobs", "is_stretch",      "INTEGER DEFAULT 0"),
        ("jobs", "skills_stretch",  "TEXT"),
        ("jobs", "role_variant",    "TEXT"),
    ]
    if USE_PG:
        for table, col, defn in migrations:
            try:
                conn._cur.execute(
                    f"ALTER TABLE {table} ADD COLUMN {col} {defn}"
                )
                conn._pg.commit()
            except Exception:
                conn._pg.rollback()   # column already exists — ignore
    else:
        # SQLite: check pragma then add
        existing = {
            row[1]
            for row in conn._sq.execute("PRAGMA table_info(jobs)").fetchall()
        }
        for table, col, defn in migrations:
            if col not in existing:
                conn._sq.execute(f"ALTER TABLE {table} ADD COLUMN {col} {defn}")


# ═══════════════════════════════════════════════════════════════════════════
# USERS
# ═══════════════════════════════════════════════════════════════════════════

def get_user_by_email(email: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE email=?", (email.lower(),)).fetchone()
    conn.close()
    return row  # already dict or None


def get_user_by_id(user_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return row


def create_user(email: str, password_hash: str, name: str = "", is_admin: bool = False) -> int:
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO users (email, password_hash, name, is_admin, created_at) VALUES (?,?,?,?,?)",
        (email.lower(), password_hash, name, 1 if is_admin else 0, _now())
    )
    if USE_PG:
        conn._cur.execute("SELECT id FROM users WHERE email=%s", (email.lower(),))
        user_id = conn._cur.fetchone()["id"]
    else:
        user_id = conn._sq_cur.lastrowid
    conn.execute("UPDATE invite_whitelist SET used=1 WHERE email=?", (email.lower(),))
    _seed_user_settings(conn, user_id)
    conn.commit()
    conn.close()
    return user_id


def _seed_user_settings(conn: _Conn, user_id: int):
    defaults = [
        ("gmail_address", ""), ("gmail_app_password", ""),
        ("user_name", ""), ("user_skills", ""),
        ("user_experience_years", "0"), ("user_preferred_locations", ""),
        ("user_salary_target", "0"), ("notice_period", ""),
        ("resume_summary", ""), ("resume_text", ""),
        ("last_search_role", ""), ("last_search_country", "IN"),
        ("last_search_locations", ""),
    ]
    for key, val in defaults:
        conn.execute(
            "INSERT OR IGNORE INTO settings (user_id, key, value) VALUES (?,?,?)",
            (user_id, key, val)
        )


# ── Whitelist ──────────────────────────────────────────────────────────────

def is_whitelisted(email: str) -> bool:
    conn = get_connection()
    row = conn.execute("SELECT 1 FROM invite_whitelist WHERE email=?", (email.lower(),)).fetchone()
    conn.close()
    return row is not None


def add_to_whitelist(email: str):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO invite_whitelist (email, added_at) VALUES (?,?)",
        (email.lower(), _now())
    )
    conn.commit()
    conn.close()


def remove_from_whitelist(email: str):
    conn = get_connection()
    conn.execute("DELETE FROM invite_whitelist WHERE email=?", (email.lower(),))
    conn.commit()
    conn.close()


def list_whitelist() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM invite_whitelist ORDER BY added_at DESC").fetchall()
    conn.close()
    return rows


# ═══════════════════════════════════════════════════════════════════════════
# SETTINGS (per-user)
# ═══════════════════════════════════════════════════════════════════════════

def get_settings(user_id: int) -> dict:
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM settings WHERE user_id=?", (user_id,)).fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def save_settings(user_id: int, updates: dict):
    conn = get_connection()
    for key, value in updates.items():
        conn.execute(
            "INSERT INTO settings (user_id, key, value) VALUES (?,?,?) "
            "ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value",
            (user_id, key, str(value))
        )
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# JOBS
# ═══════════════════════════════════════════════════════════════════════════

def insert_jobs(jobs: list, user_id: int) -> tuple:
    conn = get_connection()
    inserted = skipped = 0
    for job in jobs:
        job["user_id"] = user_id
        try:
            conn.execute(
                """INSERT OR IGNORE INTO jobs
                   (user_id, title, company, location, salary_min, salary_max, salary_raw,
                    salary_target, experience_required, description, description_snippet,
                    skills_required, job_url, url_hash, source, country,
                    recruiter_name, recruiter_email, match_score, match_breakdown,
                    skills_gap, skills_stretch, is_hot, is_stretch, location_match, role_variant, scraped_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    user_id,
                    job.get("title", ""),
                    job.get("company", ""),
                    job.get("location", ""),
                    job.get("salary_min"),
                    job.get("salary_max"),
                    job.get("salary_raw", ""),
                    job.get("salary_target"),
                    job.get("experience_required", ""),
                    job.get("description", ""),
                    job.get("description_snippet", ""),
                    job.get("skills_required", ""),
                    job.get("job_url", ""),
                    job.get("url_hash", ""),
                    job.get("source", ""),
                    job.get("country", "IN"),
                    job.get("recruiter_name", ""),
                    job.get("recruiter_email", ""),
                    job.get("match_score", 0),
                    job.get("match_breakdown", "{}"),
                    job.get("skills_gap", ""),
                    job.get("skills_stretch", ""),
                    job.get("is_hot", 0),
                    job.get("is_stretch", 0),
                    job.get("location_match", 0),
                    job.get("role_variant", ""),
                    job.get("scraped_at", _now()),
                ),
            )
            if conn.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1
    conn.commit()
    conn.close()
    return inserted, skipped


def get_jobs(user_id: int, status=None, source=None, country=None,
             min_score=None, followup_due=False, page=1, per_page=20, sort="score") -> tuple:
    conn = get_connection()
    conditions = ["user_id = ?"]
    params: list = [user_id]

    if status:
        conditions.append("status = ?"); params.append(status)
    if source:
        conditions.append("source = ?"); params.append(source)
    if country:
        conditions.append("country = ?"); params.append(country)
    if min_score is not None:
        conditions.append("match_score >= ?"); params.append(min_score)
    if followup_due:
        if USE_PG:
            conditions.append("followup_due_at IS NOT NULL AND followup_due_at <= NOW()")
        else:
            conditions.append("followup_due_at IS NOT NULL AND followup_due_at <= datetime('now')")

    where = "WHERE " + " AND ".join(conditions)
    order = {
        "score": "location_match DESC, match_score DESC, scraped_at DESC",
        "hot":   "is_hot DESC, location_match DESC, scraped_at DESC",
        "date":  "scraped_at DESC",
    }.get(sort, "location_match DESC, match_score DESC")

    total = conn.execute("SELECT COUNT(*) as cnt FROM jobs {}".format(where), params).fetchone()["cnt"]
    offset = (page - 1) * per_page
    rows = conn.execute(
        "SELECT * FROM jobs {} ORDER BY {} LIMIT ? OFFSET ?".format(where, order),
        params + [per_page, offset]
    ).fetchall()
    conn.close()
    return rows, total


def get_job_detail(job_id: int, user_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM jobs WHERE id=? AND user_id=?", (job_id, user_id)).fetchone()
    conn.close()
    return row


def update_job(job_id: int, user_id: int, updates: dict):
    conn = get_connection()
    if USE_PG:
        fields = ", ".join("{} = %s".format(k) for k in updates)
        sql    = "UPDATE jobs SET {} WHERE id=%s AND user_id=%s".format(fields)
    else:
        fields = ", ".join("{} = ?".format(k) for k in updates)
        sql    = "UPDATE jobs SET {} WHERE id=? AND user_id=?".format(fields)
    values = list(updates.values()) + [job_id, user_id]
    if USE_PG:
        conn._cur.execute(sql, values)
    else:
        conn._sq.execute(sql, values)
    conn.commit()
    conn.close()


def get_stats(user_id: int) -> dict:
    conn = get_connection()
    rows  = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM jobs WHERE user_id=? GROUP BY status", (user_id,)
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) as cnt FROM jobs WHERE user_id=?", (user_id,)).fetchone()["cnt"]
    conn.close()
    stats = {r["status"]: r["cnt"] for r in rows}
    stats["total"] = total
    return stats


def get_followup_due(user_id: int) -> list:
    conn = get_connection()
    now_expr = "NOW()" if USE_PG else "datetime('now')"
    rows = conn.execute(
        "SELECT * FROM jobs WHERE user_id=? AND followup_due_at IS NOT NULL "
        "AND followup_due_at <= {} ORDER BY followup_due_at ASC".format(now_expr),
        (user_id,)
    ).fetchall()
    conn.close()
    return rows


def clear_jobs(user_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM jobs WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def export_jobs_csv(user_id: int) -> str:
    conn = get_connection()
    rows = conn.execute(
        "SELECT title, company, location, salary_raw, match_score, status, job_url, source, scraped_at "
        "FROM jobs WHERE user_id=? ORDER BY match_score DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    headers = ["title", "company", "location", "salary", "score", "status", "url", "source", "scraped_at"]
    lines = [",".join(headers)]
    for r in rows:
        lines.append(",".join(
            '"{}"'.format(str(r.get(h) or r.get(k, "") or "").replace('"', '""'))
            for h, k in zip(headers, ["title","company","location","salary_raw","match_score","status","job_url","source","scraped_at"])
        ))
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# SOCIAL POSTS
# ═══════════════════════════════════════════════════════════════════════════

def insert_social_posts(posts: list, user_id: int) -> tuple:
    conn = get_connection()
    inserted = skipped = 0
    for post in posts:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO social_posts
                   (user_id, poster_name, poster_email, poster_profile_url, company,
                    role_mentioned, post_text, post_url, source, country,
                    legitimacy_score, scraped_at, status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    user_id,
                    post.get("poster_name", ""),
                    post.get("poster_email", ""),
                    post.get("poster_profile_url", ""),
                    post.get("company", ""),
                    post.get("role_mentioned", ""),
                    post.get("post_text", ""),
                    post["post_url"],
                    post["source"],
                    post.get("country", "IN"),
                    post.get("legitimacy_score", 0),
                    post["scraped_at"],
                    "new",
                ),
            )
            if conn.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1
    conn.commit()
    conn.close()
    return inserted, skipped


def get_social_posts(user_id: int, source=None, status=None, page=1, per_page=20) -> tuple:
    conn = get_connection()
    conditions = ["user_id = ?"]
    params: list = [user_id]
    if source and source != "all":
        conditions.append("source = ?"); params.append(source)
    if status and status != "all":
        conditions.append("status = ?"); params.append(status)

    where = "WHERE " + " AND ".join(conditions)
    total = conn.execute("SELECT COUNT(*) as cnt FROM social_posts {}".format(where), params).fetchone()["cnt"]
    offset = (page - 1) * per_page
    rows = conn.execute(
        "SELECT * FROM social_posts {} ORDER BY scraped_at DESC LIMIT ? OFFSET ?".format(where),
        params + [per_page, offset]
    ).fetchall()
    conn.close()
    return rows, total


def update_social_post(post_id: int, user_id: int, updates: dict):
    conn = get_connection()
    if USE_PG:
        fields = ", ".join("{} = %s".format(k) for k in updates)
        sql    = "UPDATE social_posts SET {} WHERE id=%s AND user_id=%s".format(fields)
        conn._cur.execute(sql, list(updates.values()) + [post_id, user_id])
    else:
        fields = ", ".join("{} = ?".format(k) for k in updates)
        conn._sq.execute("UPDATE social_posts SET {} WHERE id=? AND user_id=?".format(fields),
                         list(updates.values()) + [post_id, user_id])
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════

def get_analytics(user_id: int) -> dict:
    conn = get_connection()
    total     = conn.execute("SELECT COUNT(*) as cnt FROM jobs WHERE user_id=?", (user_id,)).fetchone()["cnt"]
    applied   = conn.execute("SELECT COUNT(*) as cnt FROM jobs WHERE user_id=? AND status='applied'", (user_id,)).fetchone()["cnt"]
    interview = conn.execute("SELECT COUNT(*) as cnt FROM jobs WHERE user_id=? AND status='interview'", (user_id,)).fetchone()["cnt"]

    by_source = conn.execute(
        "SELECT source, COUNT(*) as cnt FROM jobs WHERE user_id=? GROUP BY source ORDER BY cnt DESC",
        (user_id,)
    ).fetchall()

    all_gaps = conn.execute(
        "SELECT skills_gap FROM jobs WHERE user_id=? AND skills_gap != ''", (user_id,)
    ).fetchall()
    gap_counts: dict = {}
    for row in all_gaps:
        for skill in (row.get("skills_gap") or "").split(","):
            s = skill.strip().lower()
            if s:
                gap_counts[s] = gap_counts.get(s, 0) + 1
    top_gaps = sorted(gap_counts.items(), key=lambda x: -x[1])[:10]

    score_dist = conn.execute(
        """SELECT
            SUM(CASE WHEN match_score >= 70 THEN 1 ELSE 0 END) as high,
            SUM(CASE WHEN match_score >= 40 AND match_score < 70 THEN 1 ELSE 0 END) as mid,
            SUM(CASE WHEN match_score < 40 THEN 1 ELSE 0 END) as low
           FROM jobs WHERE user_id=?""",
        (user_id,)
    ).fetchone()

    conn.close()
    return {
        "total_saved":    total,
        "applied":        applied,
        "interviews":     interview,
        "response_rate":  round((interview / applied * 100) if applied else 0, 1),
        "by_source":      by_source,
        "top_skill_gaps": [{"skill": s, "count": c} for s, c in top_gaps],
        "score_distribution": {
            "high": score_dist.get("high") or 0,
            "mid":  score_dist.get("mid")  or 0,
            "low":  score_dist.get("low")  or 0,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# COMPANY CACHE
# ═══════════════════════════════════════════════════════════════════════════

def get_company_cache(company_slug: str, role: str = ""):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM company_cache WHERE company_slug=? AND role=?", (company_slug, role)
    ).fetchone()
    conn.close()
    return row


def save_company_cache(data: dict):
    conn = get_connection()
    conn.execute(
        """INSERT INTO company_cache
           (company_slug, role, avg_salary_min, avg_salary_max, rating,
            review_count, review_summary, source, cached_at)
           VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(company_slug, role) DO UPDATE SET
             avg_salary_min=excluded.avg_salary_min,
             avg_salary_max=excluded.avg_salary_max,
             rating=excluded.rating,
             review_count=excluded.review_count,
             review_summary=excluded.review_summary,
             cached_at=excluded.cached_at""",
        (
            data["company_slug"], data.get("role", ""),
            data.get("avg_salary_min"), data.get("avg_salary_max"),
            data.get("rating"), data.get("review_count", 0),
            data.get("review_summary", ""), data.get("source", "ambitionbox"),
            _now()
        )
    )
    conn.commit()
    conn.close()
