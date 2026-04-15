from __future__ import annotations
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.database import init_db
from backend.routes.auth          import router as auth_router
from backend.routes.jobs          import router as jobs_router
from backend.routes.search        import router as search_router
from backend.routes.email_route   import router as email_router
from backend.routes.settings_route import router as settings_router
from backend.routes.followup      import router as followup_router
from backend.routes.resume        import router as resume_router
from backend.routes.social        import router as social_router
from backend.routes.analytics     import router as analytics_router
from backend.routes.company       import router as company_router
from backend.routes.recruiter     import router as recruiter_router

app = FastAPI(title="Job Hunter", version="4.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in [auth_router, jobs_router, search_router, email_router,
          settings_router, followup_router, resume_router, social_router,
          analytics_router, company_router, recruiter_router]:
    app.include_router(r)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/api/health")
def health():
    import os, traceback
    # Show all env vars containing db-related keys (masked)
    db_vars = {k: (v[:20] + "..." if len(v) > 20 else v)
               for k, v in os.environ.items()
               if any(x in k.upper() for x in ["DATABASE", "POSTGRES", "PG", "DB_"])}
    db_url = os.environ.get("DATABASE_URL", "")
    use_pg = bool(db_url)
    try:
        from backend.database import get_connection, USE_PG as module_use_pg, DATABASE_URL as module_db_url
        conn = get_connection()
        if use_pg:
            conn._cur.execute("SELECT 1 as ok")
            result = conn._cur.fetchone()
        else:
            result = conn.execute("SELECT 1 as ok").fetchone()
        conn.close()
        return {
            "status": "ok",
            "backend": "postgres" if use_pg else "sqlite",
            "db_url_set": bool(db_url),
            "module_use_pg": module_use_pg,
            "module_db_url_set": bool(module_db_url),
            "db_related_vars": db_vars,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "trace": traceback.format_exc(),
                "db_related_vars": db_vars}


@app.get("/")
def serve_frontend():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.on_event("startup")
def on_startup():
    init_db()
