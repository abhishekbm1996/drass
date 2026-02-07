"""Pytest fixtures: isolated DB per test, FastAPI TestClient."""
import os

import pytest
from fastapi.testclient import TestClient

# Set test DB before importing app so startup uses it
@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    os.environ["ATTENTION_TRACKER_DB"] = db_path
    from server import database
    database.init_db()
    from server.main import app
    with TestClient(app) as c:
        yield c
    os.environ.pop("ATTENTION_TRACKER_DB", None)
