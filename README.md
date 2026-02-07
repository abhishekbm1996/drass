# Attention Tracker

A minimal, self-hosted web app to consciously track attention breaks during work sessions and surface focus patterns over time. Start a session, tap “I got distracted” when you slip, then end the session to see duration, distraction count, and focus streaks. View a simple dashboard of today’s stats and a 7-day trend.

## Tech stack

- **Backend:** Python, FastAPI, uvicorn
- **Database:** SQLite (stdlib `sqlite3`)
- **Frontend:** Vanilla HTML, CSS, JavaScript
- **PWA:** Service worker + manifest for “Add to Home Screen” on iOS Safari

No auth — single-user MVP.

## Setup

1. Clone the repo and go into the project directory:
   ```bash
   cd attention-tracker
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

4. (Optional) Use a separate data directory for the SQLite DB by setting an env var or editing `server/database.py`; by default the DB file is `attention_tracker.db` in the project root.

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
attention-tracker/
├── server/
│   ├── main.py       # FastAPI app, static mount, API routes
│   ├── database.py   # SQLite schema and CRUD
│   └── models.py     # Pydantic request/response models
├── static/
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   ├── manifest.json
│   ├── service-worker.js
│   └── favicon.svg
├── requirements.txt
├── README.md
└── .gitignore
```

## API

- `POST /api/sessions` — Start a new session
- `PATCH /api/sessions/{id}` — End a session
- `GET /api/sessions/{id}/summary` — Session summary (duration, distractions, streaks)
- `POST /api/sessions/{id}/distractions` — Log a distraction
- `GET /api/stats` — Dashboard stats (today + last 7 days)

## Roadmap

- Optional auth for multi-user or multi-device
- Data export (e.g. CSV/JSON)
- Sync across devices (e.g. optional cloud backup)

## License

See [LICENSE](LICENSE).
