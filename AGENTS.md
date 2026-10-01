# BUILT BY DESIGN — Assessment Tool

## What this is
Assessment app: `index.html` (7 pillars x 10 Likert questions, autosave, team roster
aggregation, print-ready report) plus a FastAPI backend (`api/`) that captures every
participant session in real time, and `dashboard.html` — a live results dashboard.

## Run
`docker compose -f docker-compose.base44.yml up -d`
- `web` (nginx) serves index.html + dashboard.html on host port 3000 and proxies `/api/*` to the `api` service.
- `api` (uvicorn --reload, source bind-mounted) stores sessions in SQLite at volume `api-data:/data/assessment.db`.
- Edits to index.html/dashboard.html show on refresh; edits to api/main.py hot-reload via uvicorn --reload.

## Endpoints
- POST /api/session — create participant session (returns `{id}`)
- PUT /api/session/{id} — save answers + meta (called on every Next/Back/Jump/Exit)
- GET /api/session/{id} — restore draft (used by "Resume Draft")
- GET /api/dashboard — requires header `X-Dashboard-Key` = DASHBOARD_PASSWORD secret
- GET /api/healthz

## Verify
`curl -s localhost:3000 | head -3` → doctype of the BUILT BY DESIGN page.
`curl -s localhost:3000/api/healthz` → `{"ok": true, ...}`.
Dashboard: open /dashboard, passcode from the DASHBOARD_PASSWORD secret.

## Quirks
- index.html and dashboard.html use CRLF line endings — multi-line find/replace must account for `\r\n`.
- Frontend state keys: `bbd_team_roster_v1`, `bbd_current_draft_v1`, `bbd_session_id_v1`.
- Server sync is save-on-navigation (Next/Back/Jump/Exit/final question); radio clicks alone do not sync.
- Question bank `BBD_BANK` renders wording per lens (athletic/education/corporate/church).
- Scoring: answers are 1–5, weighted ×1.4 → 70 pts per pillar, 490 total (classification 238/364, pillar bands 35/49/63). Rules duplicated in api/main.py — keep in sync with index.html. Pre-v2 roster records and server rows are migrated/rescored automatically.
