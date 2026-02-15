"""Vercel entrypoint: export FastAPI app for serverless deployment."""
import os
import sys
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

app = FastAPI()

@app.get("/api/debug")
def debug():
    info = []
    info.append(f"Python: {sys.version}")

    db_url = os.environ.get("DATABASE_POSTGRES_URL", "")
    info.append(f"DB URL set: {bool(db_url)}")

    if db_url:
        parsed = urlparse(db_url)
        info.append(f"URL scheme: {parsed.scheme}")
        info.append(f"URL user: {parsed.username}")
        info.append(f"URL host: {parsed.hostname}")
        info.append(f"URL port: {parsed.port}")
        info.append(f"URL dbname: {parsed.path}")

        import psycopg2

        # Test 1: Connect with URL string (current approach)
        try:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            cur.execute("SELECT 1")
            info.append("Test 1 (URL string): OK")
            conn.close()
        except Exception as e:
            info.append(f"Test 1 (URL string): FAILED - {e}")

        # Test 2: Connect with explicit params
        try:
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port,
                user=parsed.username,
                password=parsed.password,
                dbname=parsed.path.lstrip("/"),
            )
            cur = conn.cursor()
            cur.execute("SELECT 1")
            info.append("Test 2 (explicit params): OK")
            conn.close()
        except Exception as e:
            info.append(f"Test 2 (explicit params): FAILED - {e}")

        # Test 3: Try session mode (port 5432) if currently on 6543
        if parsed.port == 6543:
            try:
                conn = psycopg2.connect(
                    host=parsed.hostname,
                    port=5432,
                    user=parsed.username,
                    password=parsed.password,
                    dbname=parsed.path.lstrip("/"),
                )
                cur = conn.cursor()
                cur.execute("SELECT 1")
                info.append("Test 3 (session mode 5432): OK")
                conn.close()
            except Exception as e:
                info.append(f"Test 3 (session mode 5432): FAILED - {e}")

    return PlainTextResponse("\n".join(info))

@app.get("/{path:path}")
def catch_all(path: str):
    return PlainTextResponse("Debug app. Visit /api/debug")
