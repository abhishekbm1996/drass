"""Vercel entrypoint: export FastAPI app for serverless deployment."""
import os
import sys

# Minimal test: does the Python runtime even work?
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

app = FastAPI()

@app.get("/api/debug")
def debug():
    info = []
    info.append(f"Python: {sys.version}")
    info.append(f"Env keys with DB/PG/SUPA: {[k for k in os.environ if any(x in k.upper() for x in ['DATABASE','PG','SUPA','DB'])]}")
    info.append(f"DATABASE_POSTGRES_URL set: {bool(os.environ.get('DATABASE_POSTGRES_URL'))}")

    # Test psycopg2 import
    try:
        import psycopg2
        info.append(f"psycopg2 version: {psycopg2.__version__}")
    except Exception as e:
        info.append(f"psycopg2 import FAILED: {e}")

    # Test DB connection
    db_url = os.environ.get("DATABASE_POSTGRES_URL")
    if db_url:
        info.append(f"DB URL prefix: {db_url[:40]}...")
        try:
            import psycopg2
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            cur.execute("SELECT 1")
            info.append(f"DB connection: OK")
            conn.close()
        except Exception as e:
            info.append(f"DB connection FAILED: {e}")
    else:
        info.append("No DATABASE_POSTGRES_URL found")

    return PlainTextResponse("\n".join(info))

@app.get("/{path:path}")
def catch_all(path: str):
    return PlainTextResponse("Minimal debug app running. Visit /api/debug")
