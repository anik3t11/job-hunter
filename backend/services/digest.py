from __future__ import annotations
"""
Job Alert Email Digest — sends daily/weekly digest of new matching jobs.
Scheduled via APScheduler in main.py (runs at 8am daily).
"""
import logging
from datetime import datetime, timezone, timedelta

from backend.database import get_connection, get_settings
from backend.services.email_sender import send_email

logger = logging.getLogger(__name__)


def get_new_jobs_since(user_id: int, hours: int = 24, min_score: int = 50) -> list[dict]:
    """Return jobs scraped in last N hours with score >= min_score, status = new."""
    conn = get_connection()
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        rows = conn.execute(
            """SELECT id, title, company, location, match_score, job_url, source, salary_raw, scraped_at
               FROM jobs
               WHERE user_id=? AND status='new' AND match_score>=? AND scraped_at>=?
               ORDER BY match_score DESC
               LIMIT 30""",
            (user_id, min_score, cutoff),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _score_color(score: int) -> str:
    if score >= 70:
        return "#059669"
    if score >= 40:
        return "#d97706"
    return "#e11d48"


def build_digest_html(user_name: str, jobs: list[dict], role: str = "") -> str:
    """Build a clean HTML email body."""
    count = len(jobs)
    role_line = f" for <strong>{role}</strong>" if role else ""
    rows_html = ""
    for j in jobs:
        score = j.get("match_score", 0)
        color = _score_color(score)
        salary = j.get("salary_raw") or ""
        location = j.get("location") or ""
        meta = " · ".join(filter(None, [location, salary]))
        rows_html += f"""
        <tr>
          <td style="padding:12px 8px;border-bottom:1px solid #f0f0f0;vertical-align:top">
            <div style="font-weight:600;font-size:14px;color:#111">{j.get('title','')}</div>
            <div style="font-size:12px;color:#555;margin-top:2px">{j.get('company','')} · {meta}</div>
          </td>
          <td style="padding:12px 8px;border-bottom:1px solid #f0f0f0;text-align:center;vertical-align:top;white-space:nowrap">
            <span style="background:{color};color:#fff;padding:3px 8px;border-radius:9999px;font-size:12px;font-weight:700">{score}</span>
          </td>
          <td style="padding:12px 8px;border-bottom:1px solid #f0f0f0;vertical-align:top">
            <a href="{j.get('job_url','#')}" style="color:#6366f1;font-size:13px;text-decoration:none">View →</a>
          </td>
        </tr>"""

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"/></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8f9fa;margin:0;padding:0">
  <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08)">
    <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:28px 32px">
      <div style="font-size:22px;font-weight:800;color:#fff">📋 Job Hunter</div>
      <div style="font-size:14px;color:rgba(255,255,255,.85);margin-top:4px">Your daily job digest</div>
    </div>
    <div style="padding:28px 32px">
      <p style="font-size:15px;color:#333;margin:0 0 20px">
        Hi {user_name or 'there'} 👋 — <strong>{count} new job{'' if count==1 else 's'}</strong>{role_line} match your profile today.
      </p>
      <table style="width:100%;border-collapse:collapse">
        <thead>
          <tr style="background:#f8f9fa">
            <th style="padding:8px;text-align:left;font-size:11px;font-weight:700;color:#888;text-transform:uppercase">Job</th>
            <th style="padding:8px;text-align:center;font-size:11px;font-weight:700;color:#888;text-transform:uppercase">Score</th>
            <th style="padding:8px;font-size:11px;font-weight:700;color:#888;text-transform:uppercase">Link</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
      <div style="margin-top:24px;text-align:center">
        <a href="https://web-production-3b2ec.up.railway.app"
           style="display:inline-block;background:#6366f1;color:#fff;padding:12px 28px;border-radius:8px;font-weight:600;text-decoration:none;font-size:14px">
          Open Job Hunter →
        </a>
      </div>
      <p style="font-size:11px;color:#aaa;text-align:center;margin-top:24px">
        To stop these emails, disable Job Alerts in Settings.
      </p>
    </div>
  </div>
</body>
</html>"""


def send_digest_for_user(user_id: int) -> dict:
    """Send digest email to a single user. Returns status dict."""
    try:
        s = get_settings(user_id)
        if not s.get("alert_enabled", "1") == "1":
            return {"sent": False, "reason": "alerts disabled"}

        gmail = s.get("gmail_address", "")
        pwd   = s.get("gmail_app_password", "")
        if not gmail or not pwd:
            return {"sent": False, "reason": "no gmail configured"}

        min_score = int(s.get("alert_min_score", 50) or 50)
        freq      = s.get("alert_frequency", "daily")
        hours     = 168 if freq == "weekly" else 24

        jobs = get_new_jobs_since(user_id, hours=hours, min_score=min_score)
        if not jobs:
            return {"sent": False, "reason": "no new jobs", "jobs_count": 0}

        role     = s.get("last_search_role", "") or ""
        name     = s.get("user_name", "") or ""
        html     = build_digest_html(name, jobs, role)
        subject  = f"📋 {len(jobs)} new job match{'es' if len(jobs)!=1 else ''} today — Job Hunter"

        # Use HTML email — need to update send_email to support HTML
        ok, msg = _send_html_email(gmail, pwd, gmail, subject, html)
        return {"sent": ok, "jobs_count": len(jobs), "message": msg}
    except Exception as e:
        logger.error(f"digest error for user {user_id}: {e}")
        return {"sent": False, "reason": str(e)}


def _send_html_email(gmail_address, gmail_app_password, to_email, subject, html_body) -> tuple:
    """Send HTML email via Gmail SMTP."""
    import smtplib, ssl
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    if not gmail_address or not gmail_app_password:
        return False, "Gmail credentials not configured."
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = gmail_address
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(gmail_address, gmail_app_password)
            server.sendmail(gmail_address, to_email, msg.as_string())
        return True, "Sent."
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail auth failed — check App Password in Settings."
    except Exception as e:
        return False, str(e)


def send_all_digests():
    """Called by scheduler — send digests to all eligible users."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT DISTINCT user_id FROM settings WHERE key='alert_enabled' AND value='1'").fetchall()
        user_ids = [r["user_id"] for r in rows]
    finally:
        conn.close()

    sent = skipped = errors = 0
    for uid in user_ids:
        result = send_digest_for_user(uid)
        if result.get("sent"):
            sent += 1
        elif "reason" in result and result["reason"] not in ("alerts disabled", "no gmail configured"):
            skipped += 1
        else:
            skipped += 1
    logger.info(f"Digest run complete: {sent} sent, {skipped} skipped, {errors} errors")
