from typing import Optional

from pydantic import BaseModel


class SessionResponse(BaseModel):
    id: int
    started_at: str
    ended_at: Optional[str] = None


class DistractionResponse(BaseModel):
    id: int
    session_id: int
    created_at: str


class DayTrend(BaseModel):
    date: str
    session_count: int
    total_distractions: int
    longest_streak_seconds: float


class SessionSummaryResponse(BaseModel):
    duration_seconds: float
    distraction_count: int
    average_streak_seconds: float
    longest_streak_seconds: float


class StatsResponse(BaseModel):
    today_sessions: int
    today_distractions_per_hour: float
    today_longest_streak_seconds: float
    last_7_days: list[DayTrend]
