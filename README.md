# Drass

Drass is a minimal, self-hosted web app to consciously track attention breaks during work sessions and surface focus patterns over time. Named after a place in Ladakh—cold, clear, rocky. Start a session, tap “I got distracted” when you slip, then end the session to see duration, distraction count, and focus streaks. View a simple dashboard of today’s stats and a 7-day trend.

## Tech stack

- **Backend:** Python, FastAPI, uvicorn
- **Database:** PostgreSQL (production/Vercel) or SQLite (local dev)
- **Frontend:** Vanilla HTML, CSS, JavaScript
- **PWA:** Service worker + manifest for “Add to Home Screen” on iOS Safari
- **Auth:** HTTP Basic Auth when `BASIC_AUTH_USER` and `BASIC_AUTH_PASSWORD` are set (optional, for public deployments)

## Setup

1. Clone the repo and go into the project directory:
   ```bash
   cd drass
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # macOS/Linux
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. (Optional) Use a separate data directory for the SQLite DB: set `ATTENTION_TRACKER_DB` to a file path. Default is `attention_tracker.db` in the project root.

## Deploy to Vercel

1. Create a free Postgres database (e.g. [Neon](https://neon.tech), [Supabase](https://supabase.com), or [Vercel Postgres](https://vercel.com/storage/postgres)).
2. [Connect your Git repo to Vercel](https://vercel.com/new) and deploy.
3. In Vercel Project Settings → Environment Variables, add:
   - `DATABASE_URL` — your Postgres connection string (e.g. `postgresql://user:pass@host/dbname`)
   - `BASIC_AUTH_USER` — username for HTTP Basic Auth (required for public deployments)
   - `BASIC_AUTH_PASSWORD` — password for HTTP Basic Auth
4. Redeploy. The app will use Postgres and Basic Auth. Visitors will see a browser login prompt.

**Local dev:** Without `DATABASE_URL`, the app uses SQLite. Without `BASIC_AUTH_*`, there is no auth prompt.

## Testing

Tests use an isolated SQLite DB per run (via `ATTENTION_TRACKER_DB` in tests). Install dev dependencies and run pytest:

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

CI runs on push/PR to `main` or `master` (see [.github/workflows/ci.yml](.github/workflows/ci.yml)).

## Run locally

From the project root (with `venv` activated):

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

- **On this Mac:** open [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **From another device on the same WiFi:** find your Mac’s local IP (e.g. **System Settings → Network → Wi‑Fi → Details**), then on the other device open `http://<MAC_IP>:8000` (e.g. `http://192.168.1.5:8000`)

Binding to `0.0.0.0` is required so the server is reachable from your phone or other machines on the network.

## Access from iPhone on the same WiFi

1. On your Mac, run the server with the command above and note your Mac’s local IP (e.g. `192.168.1.5`).
2. On your iPhone, connect to the same Wi‑Fi network, open Safari, and go to `http://<MAC_IP>:8000`.
3. To install as a PWA: in Safari, tap **Share → Add to Home Screen**. The app will open in standalone mode and you can use it like a native app.

## Project structure

```
drass/
├── .github/workflows/
│   └── ci.yml        # Run tests on push/PR
├── server/
│   ├── main.py       # FastAPI app, static mount, API routes, Basic Auth
│   ├── database.py   # SQLite (dev) or Postgres (prod) schema and CRUD
│   └── models.py     # Pydantic request/response models
├── static/
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   ├── manifest.json
│   ├── service-worker.js
│   └── favicon.svg
├── tests/
│   ├── conftest.py   # Pytest fixtures (client, isolated DB)
│   └── test_api.py   # API contract and behavior tests
├── index.py          # Vercel entrypoint
├── vercel.json       # Vercel config
├── requirements.txt
├── requirements-dev.txt
├── README.md
└── .gitignore
```

## API

- `GET /api/sessions/active` — Current active session (if any); used to restore state on refresh
- `POST /api/sessions` — Start a new session
- `PATCH /api/sessions/{id}` — End a session
- `GET /api/sessions/{id}/summary` — Session summary (duration, distractions, streaks)
- `POST /api/sessions/{id}/distractions` — Log a distraction
- `GET /api/stats` — Dashboard stats (today + last 7 days)

## Roadmap

- OAuth (Google/GitHub) as an alternative to Basic Auth
- Data export (e.g. CSV/JSON)
- Sync across devices (e.g. optional cloud backup)

## License

See [LICENSE](LICENSE).
