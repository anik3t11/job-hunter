from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.database import init_db
from backend.routes.jobs import router as jobs_router
from backend.routes.search import router as search_router
from backend.routes.email_route import router as email_router
from backend.routes.settings_route import router as settings_router
from backend.routes.followup import router as followup_router
from backend.routes.resume import router as resume_router
from backend.routes.social import router as social_router

app = FastAPI(title="Job Hunter", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router)
app.include_router(search_router)
app.include_router(email_router)
app.include_router(settings_router)
app.include_router(followup_router)
app.include_router(resume_router)
app.include_router(social_router)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def serve_frontend():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.on_event("startup")
def on_startup():
    init_db()
