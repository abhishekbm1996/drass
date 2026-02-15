import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# India Standard Time (UTC+5:30) for "today" and stats
IST = timezone(timedelta(hours=5, minutes=30))

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "attention_tracker.db"

# Use Postgres when DATABASE_URL, DATABASE_POSTGRES_URL, or SUPABASE_DB_URL is set (Vercel + Supabase)
_DB_URL = (
    os.environ.get("DATABASE_URL")
    or os.environ.get("DATABASE_POSTGRES_URL")
    or os.environ.get("SUPABASE_DB_URL")
)
USE_PG = bool(_DB_URL)


def _get_db_path():
    return os.environ.get("ATTENTION_TRACKER_DB", str(_DEFAULT_DB_PATH))


def _pg_conn():
    import psycopg2
    from psycopg2.extras import RealDictCursor
    return psycopg2.connect(_DB_URL, cursor_factory=RealDictCursor)


def _sqlite_conn():
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def get_connection():
    if USE_PG:
        return _pg_conn()
    return _sqlite_conn()


def _pg_row_to_dict(row):
    return dict(row) if row else None


def _sqlite_row_to_dict(row):
    return dict(row) if row else None


def init_db():
    conn = get_connection()
    try:
        if USE_PG:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id SERIAL PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    ended_at TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS distractions (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER NOT NULL REFERENCES sessions(id),
                    created_at TEXT NOT NULL
                )
            """)
        else:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS distractions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)
        # Indexes for performance
        if USE_PG:
            cur = conn.cursor()
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON sessions(started_at)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_ended_at ON sessions(ended_at)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_distractions_session_id ON distractions(session_id)")
        else:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON sessions(started_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_ended_at ON sessions(ended_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_distractions_session_id ON distractions(session_id)")
        conn.commit()
    finally:
        conn.close()


def create_session() -> tuple[int, str]:
    started_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = get_connection()
    try:
        if USE_PG:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO sessions (started_at, ended_at) VALUES (%s, %s) RETURNING id",
                (started_at, None),
            )
            row = cur.fetchone()
            conn.commit()
            return row["id"], started_at
        cur = conn.execute("INSERT INTO sessions (started_at, ended_at) VALUES (?, ?)", (started_at, None))
        conn.commit()
        return cur.lastrowid, started_at
    finally:
        conn.close()


ACTIVE_SESSION_MAX_AGE_HOURS = 24


def get_active_session() -> dict | None:
    conn = get_connection()
    try:
        if USE_PG:
            cur = conn.cursor()
            cur.execute(
                """SELECT s.id, s.started_at, s.ended_at, COUNT(d.id) as distraction_count
                   FROM sessions s
                   LEFT JOIN distractions d ON d.session_id = s.id
                   WHERE s.ended_at IS NULL
                   GROUP BY s.id, s.started_at, s.ended_at
                   ORDER BY s.started_at DESC LIMIT 1"""
            )
            row = cur.fetchone()
        else:
            row = conn.execute(
                """SELECT s.id, s.started_at, s.ended_at, COUNT(d.id) as distraction_count
                   FROM sessions s
                   LEFT JOIN distractions d ON d.session_id = s.id
                   WHERE s.ended_at IS NULL
                   GROUP BY s.id, s.started_at, s.ended_at
                   ORDER BY s.started_at DESC LIMIT 1"""
            ).fetchone()
        if row is None:
            return None
        row_d = _pg_row_to_dict(row) if USE_PG else _sqlite_row_to_dict(row)
        started_at_str = row_d["started_at"]
        started = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
        if started.tzinfo:
            started = started.replace(tzinfo=None)
        now = datetime.utcnow()
        age_hours = (now - started).total_seconds() / 3600
        if age_hours > ACTIVE_SESSION_MAX_AGE_HOURS:
            return None
        return {
            "id": row_d["id"],
            "started_at": started_at_str,
            "ended_at": row_d["ended_at"],
            "distraction_count": row_d["distraction_count"],
        }
    finally:
        conn.close()


def validate_and_add_distraction(session_id: int) -> tuple[int, int, str]:
    """Validate session and add distraction in a single connection."""
    created_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = get_connection()
    try:
        if USE_PG:
            cur = conn.cursor()
            cur.execute("SELECT id, ended_at FROM sessions WHERE id = %s", (session_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError("Session not found")
            if row["ended_at"]:
                raise ValueError("Session already ended")
            cur.execute(
                "INSERT INTO distractions (session_id, created_at) VALUES (%s, %s) RETURNING id",
                (session_id, created_at),
            )
            dist_row = cur.fetchone()
            conn.commit()
            return dist_row["id"], session_id, created_at
        else:
            row = conn.execute("SELECT id, ended_at FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if not row:
                raise ValueError("Session not found")
            if row["ended_at"]:
                raise ValueError("Session already ended")
            cur = conn.execute(
                "INSERT INTO distractions (session_id, created_at) VALUES (?, ?)",
                (session_id, created_at),
            )
            conn.commit()
            return cur.lastrowid, session_id, created_at
    finally:
        conn.close()


def end_session_full(session_id: int) -> dict:
    """Validate, end session, and compute summary in a single connection."""
    ended_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = get_connection()
    try:
        # Validate and update in one connection
        if USE_PG:
            cur = conn.cursor()
            cur.execute("SELECT id, started_at, ended_at FROM sessions WHERE id = %s", (session_id,))
            session = cur.fetchone()
        else:
            session = conn.execute(
                "SELECT id, started_at, ended_at FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()

        if not session:
            raise ValueError("Session not found")
        session_d = _pg_row_to_dict(session) if USE_PG else _sqlite_row_to_dict(session)
        if session_d.get("ended_at"):
            raise ValueError("Session already ended")

        # End the session
        if USE_PG:
            cur.execute("UPDATE sessions SET ended_at = %s WHERE id = %s", (ended_at, session_id))
        else:
            conn.execute("UPDATE sessions SET ended_at = ? WHERE id = ?", (ended_at, session_id))

        # Fetch distractions for summary
        if USE_PG:
            cur.execute(
                "SELECT created_at FROM distractions WHERE session_id = %s ORDER BY created_at",
                (session_id,),
            )
            dist_rows = cur.fetchall()
        else:
            dist_rows = conn.execute(
                "SELECT created_at FROM distractions WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            ).fetchall()

        conn.commit()

        dist_times = [dict(r)["created_at"] for r in dist_rows]
        start = _parse_iso(session_d["started_at"])
        end = _parse_iso(ended_at)
        duration_seconds = (end - start).total_seconds()
        count = len(dist_times)
        num_streaks = count + 1 if count > 0 else 1
        average_streak_seconds = duration_seconds / num_streaks
        longest_streak = _longest_streak_seconds(session_d["started_at"], ended_at, dist_times)

        return {
            "id": session_id,
            "started_at": session_d["started_at"],
            "ended_at": ended_at,
            "summary": {
                "duration_seconds": round(duration_seconds, 2),
                "distraction_count": count,
                "average_streak_seconds": round(average_streak_seconds, 2),
                "longest_streak_seconds": round(longest_streak, 2),
            },
        }
    finally:
        conn.close()


def get_session_summary(session_id: int) -> dict | None:
    """Get summary for an already-ended session (used by standalone summary endpoint)."""
    conn = get_connection()
    try:
        if USE_PG:
            cur = conn.cursor()
            cur.execute("SELECT id, started_at, ended_at FROM sessions WHERE id = %s", (session_id,))
            row = cur.fetchone()
            session = _pg_row_to_dict(row)
        else:
            row = conn.execute("SELECT id, started_at, ended_at FROM sessions WHERE id = ?", (session_id,)).fetchone()
            session = _sqlite_row_to_dict(row)

        if not session or not session.get("ended_at"):
            return None

        if USE_PG:
            cur.execute(
                "SELECT created_at FROM distractions WHERE session_id = %s ORDER BY created_at",
                (session_id,),
            )
            dist_rows = cur.fetchall()
        else:
            dist_rows = conn.execute(
                "SELECT created_at FROM distractions WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            ).fetchall()

        dist_times = [dict(r)["created_at"] for r in dist_rows]
        start = _parse_iso(session["started_at"])
        end = _parse_iso(session["ended_at"])
        duration_seconds = (end - start).total_seconds()
        count = len(dist_times)
        num_streaks = count + 1 if count > 0 else 1
        average_streak_seconds = duration_seconds / num_streaks
        longest_streak = _longest_streak_seconds(session["started_at"], session["ended_at"], dist_times)
        return {
            "duration_seconds": round(duration_seconds, 2),
            "distraction_count": count,
            "average_streak_seconds": round(average_streak_seconds, 2),
            "longest_streak_seconds": round(longest_streak, 2),
        }
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


def _fetch_all(conn, sql, params):
    if USE_PG:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()
    return conn.execute(sql, params).fetchall()


def _fetch_one(conn, sql, params):
    if USE_PG:
        cur = conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def _compute_day_stats(sessions, distractions_by_session):
    """Compute distraction count and longest streak for a list of sessions."""
    day_distractions = 0
    day_streaks = []
    for s in sessions:
        dist_times = distractions_by_session.get(s["id"], [])
        day_distractions += len(dist_times)
        streak = _longest_streak_seconds(s["started_at"], s["ended_at"], dist_times)
        if streak > 0 or (s["ended_at"] and not dist_times):
            day_streaks.append(streak)
    return day_distractions, day_streaks


def get_stats() -> dict:
    conn = get_connection()
    try:
        now_ist = datetime.now(IST)
        today_start_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
        now_utc = datetime.now(timezone.utc)

        # Fetch all sessions and distractions for the last 7 days in 2 queries
        week_start_ist = today_start_ist - timedelta(days=6)
        week_start_utc = week_start_ist.astimezone(timezone.utc)
        tomorrow_end_ist = today_start_ist + timedelta(days=1)
        tomorrow_end_utc = tomorrow_end_ist.astimezone(timezone.utc)
        week_start_str = week_start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        week_end_str = tomorrow_end_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

        if USE_PG:
            p = (week_start_str, week_end_str)
            all_sessions = [dict(r) for r in _fetch_all(
                conn,
                "SELECT id, started_at, ended_at FROM sessions WHERE started_at >= %s AND started_at < %s",
                p,
            )]
        else:
            p = (week_start_str, week_end_str)
            all_sessions = [dict(r) for r in _fetch_all(
                conn,
                "SELECT id, started_at, ended_at FROM sessions WHERE started_at >= ? AND started_at < ?",
                p,
            )]

        # Fetch ALL distractions for these sessions in one query (fixes N+1)
        session_ids = [s["id"] for s in all_sessions]
        distractions_by_session = defaultdict(list)
        if session_ids:
            if USE_PG:
                placeholders = ",".join(["%s"] * len(session_ids))
                dist_rows = _fetch_all(
                    conn,
                    f"SELECT session_id, created_at FROM distractions WHERE session_id IN ({placeholders}) ORDER BY created_at",
                    tuple(session_ids),
                )
            else:
                placeholders = ",".join(["?"] * len(session_ids))
                dist_rows = _fetch_all(
                    conn,
                    f"SELECT session_id, created_at FROM distractions WHERE session_id IN ({placeholders}) ORDER BY created_at",
                    tuple(session_ids),
                )
            for r in dist_rows:
                rd = dict(r)
                distractions_by_session[rd["session_id"]].append(rd["created_at"])

        # Bucket sessions by IST day
        day_buckets = defaultdict(list)
        for s in all_sessions:
            s_utc = _parse_iso(s["started_at"])
            s_ist = s_utc.astimezone(IST)
            day_key = s_ist.strftime("%Y-%m-%d")
            day_buckets[day_key].append(s)

        # Today's stats
        today_key = today_start_ist.strftime("%Y-%m-%d")
        today_sessions_list = day_buckets.get(today_key, [])
        today_distraction_count, today_streaks = _compute_day_stats(today_sessions_list, distractions_by_session)

        today_start_utc = today_start_ist.astimezone(timezone.utc)
        today_total_seconds = max(0.0, (now_utc - today_start_utc).total_seconds())
        today_hours = today_total_seconds / 3600.0 if today_total_seconds > 0 else 1.0
        today_distractions_per_hour = today_distraction_count / today_hours
        today_longest_streak = max(today_streaks) if today_streaks else 0.0

        # 7-day trend
        last_7_days = []
        for d in range(7):
            day_ist = today_start_ist - timedelta(days=d)
            day_key = day_ist.strftime("%Y-%m-%d")
            day_sessions = day_buckets.get(day_key, [])
            day_distractions, day_streaks = _compute_day_stats(day_sessions, distractions_by_session)

            last_7_days.append({
                "date": day_ist.strftime("%d-%m-%Y"),
                "session_count": len(day_sessions),
                "total_distractions": day_distractions,
                "longest_streak_seconds": max(day_streaks) if day_streaks else 0.0,
            })

        return {
            "today_sessions": len(today_sessions_list),
            "today_distractions_per_hour": round(today_distractions_per_hour, 2),
            "today_longest_streak_seconds": round(today_longest_streak, 2),
            "last_7_days": last_7_days,
        }
    finally:
        conn.close()
