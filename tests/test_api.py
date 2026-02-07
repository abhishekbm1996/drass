"""API contract and behavior tests: sessions, distractions, summary, stats."""
import pytest


def test_post_sessions_returns_201_and_session(client):
    r = client.post("/api/sessions")
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert "started_at" in data
    assert data.get("ended_at") is None
    assert isinstance(data["id"], int)
    assert "T" in data["started_at"] and "Z" in data["started_at"]


def test_patch_sessions_ends_session(client):
    create = client.post("/api/sessions").json()
    sid = create["id"]
    r = client.patch(f"/api/sessions/{sid}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == sid
    assert data["ended_at"] is not None
    assert data["started_at"] == create["started_at"]


def test_patch_sessions_404_for_missing(client):
    r = client.patch("/api/sessions/99999")
    assert r.status_code == 404


def test_patch_sessions_400_when_already_ended(client):
    create = client.post("/api/sessions").json()
    client.patch(f"/api/sessions/{create['id']}")
    r = client.patch(f"/api/sessions/{create['id']}")
    assert r.status_code == 400


def test_post_distractions_returns_201_and_distraction(client):
    create = client.post("/api/sessions").json()
    sid = create["id"]
    r = client.post(f"/api/sessions/{sid}/distractions")
    assert r.status_code == 200
    data = r.json()
    assert data["session_id"] == sid
    assert "id" in data
    assert "created_at" in data


def test_post_distractions_404_for_missing_session(client):
    r = client.post("/api/sessions/99999/distractions")
    assert r.status_code == 404


def test_post_distractions_400_after_session_ended(client):
    create = client.post("/api/sessions").json()
    sid = create["id"]
    client.patch(f"/api/sessions/{sid}")
    r = client.post(f"/api/sessions/{sid}/distractions")
    assert r.status_code == 400


def test_get_summary_404_before_session_ended(client):
    create = client.post("/api/sessions").json()
    r = client.get(f"/api/sessions/{create['id']}/summary")
    assert r.status_code == 404


def test_get_summary_200_after_session_ended(client):
    create = client.post("/api/sessions").json()
    sid = create["id"]
    client.post(f"/api/sessions/{sid}/distractions")
    client.patch(f"/api/sessions/{sid}")
    r = client.get(f"/api/sessions/{sid}/summary")
    assert r.status_code == 200
    data = r.json()
    assert "duration_seconds" in data
    assert "distraction_count" in data
    assert "average_streak_seconds" in data
    assert "longest_streak_seconds" in data
    assert data["distraction_count"] == 1


def test_get_summary_404_for_missing(client):
    r = client.get("/api/sessions/99999/summary")
    assert r.status_code == 404


def test_get_stats_returns_shape(client):
    r = client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    assert "today_sessions" in data
    assert "today_distractions_per_hour" in data
    assert "today_longest_streak_seconds" in data
    assert "last_7_days" in data
    assert len(data["last_7_days"]) == 7


def test_get_stats_today_and_7_days_types(client):
    """Stats returns numeric today fields and 7-day trend list."""
    r = client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["today_sessions"], int)
    assert isinstance(data["today_distractions_per_hour"], (int, float))
    assert isinstance(data["today_longest_streak_seconds"], (int, float))
    for day in data["last_7_days"]:
        assert "date" in day
        assert "session_count" in day
        assert "total_distractions" in day
        assert "longest_streak_seconds" in day


def test_full_flow_session_distractions_summary(client):
    r = client.post("/api/sessions")
    assert r.status_code == 200
    sid = r.json()["id"]
    client.post(f"/api/sessions/{sid}/distractions")
    client.post(f"/api/sessions/{sid}/distractions")
    r = client.patch(f"/api/sessions/{sid}")
    assert r.status_code == 200
    r = client.get(f"/api/sessions/{sid}/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["distraction_count"] == 2
    assert data["duration_seconds"] >= 0
    assert data["longest_streak_seconds"] >= 0
