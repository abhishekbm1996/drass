import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from server.database import (
    add_distraction as db_add_distraction,
    create_session as db_create_session,
    end_session as db_end_session,
    get_active_session,
    get_session,
    get_session_summary,
    get_stats,
    init_db,
)
from server.models import (
    ActiveSessionResponse,
    DayTrend,
    DistractionResponse,
    SessionResponse,
    SessionSummaryResponse,
    StatsResponse,
)

app = FastAPI(title="Drass")

# Resolve static dir relative to project root (parent of server/)
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Basic Auth when BASIC_AUTH_USER and BASIC_AUTH_PASSWORD are set (Vercel/production)
# auto_error=False so we can skip auth when env vars are unset (local dev, tests)
_scheme = HTTPBasic(auto_error=False)


def _verify_basic_auth(credentials: HTTPBasicCredentials | None = Security(_scheme)) -> None:
    user = os.environ.get("BASIC_AUTH_USER")
    password = os.environ.get("BASIC_AUTH_PASSWORD")
    if not user or not password:
        return
    if not credentials or credentials.username != user or credentials.password != password:
        raise HTTPException(status_code=401, detail="Invalid credentials", headers={"WWW-Authenticate": "Basic"})


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", dependencies=[Depends(_verify_basic_auth)])
def root():
    """Serve the SPA so PWA start_url works at /."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="static/index.html not found")
    return FileResponse(index_path)


@app.get("/service-worker.js", dependencies=[Depends(_verify_basic_auth)])
def service_worker():
    """Serve service worker at root so scope can be / for PWA caching."""
    sw_path = STATIC_DIR / "service-worker.js"
    if not sw_path.exists():
        raise HTTPException(status_code=404, detail="service-worker.js not found")
    return FileResponse(sw_path, media_type="application/javascript")


@app.get("/api/sessions/active", response_model=ActiveSessionResponse, dependencies=[Depends(_verify_basic_auth)])
def active_session():
    session = get_active_session()
    if not session:
        raise HTTPException(status_code=404, detail="No active session")
    return ActiveSessionResponse(**session)


@app.post("/api/sessions", response_model=SessionResponse, dependencies=[Depends(_verify_basic_auth)])
def start_session():
    session_id, started_at = db_create_session()
    return SessionResponse(id=session_id, started_at=started_at, ended_at=None)


@app.patch("/api/sessions/{session_id}", response_model=SessionResponse, dependencies=[Depends(_verify_basic_auth)])
def end_session(session_id: int):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get("ended_at"):
        raise HTTPException(status_code=400, detail="Session already ended")
    ended_at = db_end_session(session_id)
    return SessionResponse(
        id=session_id,
        started_at=session["started_at"],
        ended_at=ended_at,
    )


@app.get("/api/sessions/{session_id}/summary", response_model=SessionSummaryResponse, dependencies=[Depends(_verify_basic_auth)])
def session_summary(session_id: int):
    summary = get_session_summary(session_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Session not found or not ended")
    return SessionSummaryResponse(**summary)


@app.post("/api/sessions/{session_id}/distractions", response_model=DistractionResponse, dependencies=[Depends(_verify_basic_auth)])
def log_distraction(session_id: int):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get("ended_at"):
        raise HTTPException(status_code=400, detail="Session already ended")
    dist_id, sid, created_at = db_add_distraction(session_id)
    return DistractionResponse(id=dist_id, session_id=sid, created_at=created_at)


@app.get("/api/stats", response_model=StatsResponse, dependencies=[Depends(_verify_basic_auth)])
def stats():
    raw = get_stats()
    return StatsResponse(
        today_sessions=raw["today_sessions"],
        today_distractions_per_hour=raw["today_distractions_per_hour"],
        today_longest_streak_seconds=raw["today_longest_streak_seconds"],
        last_7_days=[DayTrend(**d) for d in raw["last_7_days"]],
    )
