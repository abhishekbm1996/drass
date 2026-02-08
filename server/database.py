import os
import sqlite3
from datetime import datetime, timedelta, timezone

# India Standard Time (UTC+5:30) for "today" and stats
IST = timezone(timedelta(hours=5, minutes=30))
from pathlib import Path

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "attention_tracker.db"


def _get_db_path():
    return os.environ.get("ATTENTION_TRACKER_DB", str(_DEFAULT_DB_PATH))


def get_connection():
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                ended_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS distractions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def create_session() -> tuple[int, str]:
    started_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = get_connection()
    try:
        cur = conn.execute("INSERT INTO sessions (started_at, ended_at) VALUES (?, ?)", (started_at, None))
        conn.commit()
        return cur.lastrowid, started_at
    finally:
        conn.close()


def end_session(session_id: int) -> str | None:
    ended_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = get_connection()
    try:
        conn.execute("UPDATE sessions SET ended_at = ? WHERE id = ?", (ended_at, session_id))
        conn.commit()
        return ended_at
    finally:
        conn.close()


def get_session(session_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT id, started_at, ended_at FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        return {"id": row["id"], "started_at": row["started_at"], "ended_at": row["ended_at"]}
    finally:
        conn.close()


# Max age for "active" session restore: don't treat sessions older than this as active (avoid zombie restore)
ACTIVE_SESSION_MAX_AGE_HOURS = 24


def get_active_session() -> dict | None:
    """Returns the single active session (ended_at IS NULL, started within max age) with distraction_count, or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, started_at, ended_at FROM sessions WHERE ended_at IS NULL ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        started_at_str = row["started_at"]
        started = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
        if started.tzinfo:
            started = started.replace(tzinfo=None)
        now = datetime.utcnow()
        age_hours = (now - started).total_seconds() / 3600
        if age_hours > ACTIVE_SESSION_MAX_AGE_HOURS:
            return None
        sid = row["id"]
        count = conn.execute("SELECT COUNT(*) FROM distractions WHERE session_id = ?", (sid,)).fetchone()[0]
        return {
            "id": sid,
            "started_at": started_at_str,
            "ended_at": row["ended_at"],
            "distraction_count": count,
        }
    finally:
        conn.close()


def add_distraction(session_id: int) -> tuple[int, int, str]:
    created_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO distractions (session_id, created_at) VALUES (?, ?)",
            (session_id, created_at),
        )
        conn.commit()
        return cur.lastrowid, session_id, created_at
    finally:
        conn.close()


def get_distractions_for_session(session_id: int) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, session_id, created_at FROM distractions WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ).fetchall()
        return [{"id": r["id"], "session_id": r["session_id"], "created_at": r["created_at"]} for r in rows]
    finally:
        conn.close()


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _longest_streak_seconds(started_at: str, ended_at: str | None, distraction_times: list[str]) -> float:
    if not ended_at:
        return 0.0
    start = _parse_iso(started_at)
    end = _parse_iso(ended_at)
    times = sorted([_parse_iso(t) for t in distraction_times])
    gaps = []
    if not times:
        gaps.append((end - start).total_seconds())
    else:
        gaps.append((times[0] - start).total_seconds())
        for i in range(1, len(times)):
            gaps.append((times[i] - times[i - 1]).total_seconds())
        gaps.append((end - times[-1]).total_seconds())
    return max(gaps) if gaps else 0.0


def get_session_summary(session_id: int) -> dict | None:
    """Returns duration_seconds, distraction_count, average_streak_seconds, longest_streak_seconds."""
    session = get_session(session_id)
    if not session or not session.get("ended_at"):
        return None
    distractions = get_distractions_for_session(session_id)
    dist_times = [d["created_at"] for d in distractions]
    start = _parse_iso(session["started_at"])
    end = _parse_iso(session["ended_at"])
    duration_seconds = (end - start).total_seconds()
    count = len(distractions)
    num_streaks = count + 1 if count > 0 else 1
    average_streak_seconds = duration_seconds / num_streaks
    longest_streak = _longest_streak_seconds(session["started_at"], session["ended_at"], dist_times)
    return {
        "duration_seconds": round(duration_seconds, 2),
        "distraction_count": count,
        "average_streak_seconds": round(average_streak_seconds, 2),
        "longest_streak_seconds": round(longest_streak, 2),
    }


def get_stats() -> dict:
    conn = get_connection()
    try:
        now_ist = datetime.now(IST)
        today_start_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end_ist = today_start_ist + timedelta(days=1)
        today_start_utc = today_start_ist.astimezone(timezone.utc)
        today_end_utc = today_end_ist.astimezone(timezone.utc)
        today_start_str = today_start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        today_end_str = today_end_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        now_utc = datetime.now(timezone.utc)

        # Today's sessions (started today IST)
        today_sessions = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE started_at >= ? AND started_at < ?",
            (today_start_str, today_end_str),
        ).fetchone()[0]

        # Today's distractions (from sessions that started today IST)
        rows = conn.execute(
            """
            SELECT s.id, s.started_at, s.ended_at
            FROM sessions s
            WHERE s.started_at >= ? AND s.started_at < ?
            """,
            (today_start_str, today_end_str),
        ).fetchall()

        today_distraction_count = 0
        today_streaks = []
        for row in rows:
            sid = row["id"]
            dist_rows = conn.execute(
                "SELECT created_at FROM distractions WHERE session_id = ? ORDER BY created_at",
                (sid,),
            ).fetchall()
            dist_times = [r["created_at"] for r in dist_rows]
            today_distraction_count += len(dist_times)
            streak = _longest_streak_seconds(row["started_at"], row["ended_at"], dist_times)
            if streak > 0 or (row["ended_at"] and not dist_times):
                today_streaks.append(streak)

        today_total_seconds = (now_utc - today_start_utc).total_seconds()
        today_total_seconds = max(0.0, today_total_seconds)
        today_hours = today_total_seconds / 3600.0 if today_total_seconds > 0 else 1.0
        today_distractions_per_hour = today_distraction_count / today_hours

        today_longest_streak = max(today_streaks) if today_streaks else 0.0

        # Last 7 days trend (latest date first), dates in IST, display format DD:MM:YYYY
        last_7_days = []
        for d in range(7):
            day_start_ist = today_start_ist - timedelta(days=d)
            day_end_ist = day_start_ist + timedelta(days=1)
            day_start_utc = day_start_ist.astimezone(timezone.utc)
            day_end_utc = day_end_ist.astimezone(timezone.utc)
            day_start_str = day_start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            day_end_str = day_end_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

            day_sessions = conn.execute(
                "SELECT id, started_at, ended_at FROM sessions WHERE started_at >= ? AND started_at < ?",
                (day_start_str, day_end_str),
            ).fetchall()

            day_distractions = 0
            day_streaks = []
            for row in day_sessions:
                sid = row["id"]
                dist_rows = conn.execute(
                    "SELECT created_at FROM distractions WHERE session_id = ? ORDER BY created_at",
                    (sid,),
                ).fetchall()
                dist_times = [r["created_at"] for r in dist_rows]
                day_distractions += len(dist_times)
                streak = _longest_streak_seconds(row["started_at"], row["ended_at"], dist_times)
                if streak > 0 or (row["ended_at"] and not dist_times):
                    day_streaks.append(streak)

            last_7_days.append({
                "date": day_start_ist.strftime("%d:%m:%Y"),
                "session_count": len(day_sessions),
                "total_distractions": day_distractions,
                "longest_streak_seconds": max(day_streaks) if day_streaks else 0.0,
            })

        return {
            "today_sessions": today_sessions,
            "today_distractions_per_hour": round(today_distractions_per_hour, 2),
            "today_longest_streak_seconds": round(today_longest_streak, 2),
            "last_7_days": last_7_days,
        }
    finally:
        conn.close()
