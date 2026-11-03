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
- POST /api/export/sheets — same key; posts team-summary + individual rows to a user-owned
  Google Apps Script web app (writes to the user's Google Sheet and returns its URL)
- GET /api/invite/{key} — public; returns {team, audienceType} for an active invite (404 otherwise)
- POST /api/invites, GET /api/invites, DELETE /api/invites/{key} — dashboard-key protected invite management. GET returns per-invite `started`/`completed` counts + `participants` [{name, completed}] for coach visibility.
- index.html: invite links show a personalized welcome card; finishing the last question routes to a completion screen (completePanel, showComplete()) before Results.
- GET /api/healthz

## Invite workflow
- Dashboard "Team Invites" card: create per-team keys (BBD-XXXXXX), copy link `/?key=...`, deactivate.
- index.html resolves ?key= (URL first, then localStorage `bbd_invite_key_v1`), locks team +
  audience selects, and posts the inviteKey with each session; the backend forces the session's
  team from the invite even if the client sends another. Deactivating blocks new sessions only.

## Dashboard extras
- dashboard.html has: Download Report (self-contained HTML report via Blob download),
  Export to Sheets (calls /api/export/sheets), an org-wide pillar distribution chart
  (stacked bands per pillar), and a per-team SVG pillar chart (avg bars + min–max whiskers).
- Google Sheets export secrets: GOOGLE_APPS_SCRIPT_URL (web-app URL of the script the user
  deployed from their own spreadsheet) + GOOGLE_APPS_SCRIPT_TOKEN (shared token also pasted
  into the script's TOKEN line). If either is unset, /api/export/sheets returns 503 with
  setup guidance — the app boots fine without them.

## Production deployment
- `docker-compose.prod.yml` + root `Dockerfile` (nginx prod image baking index/dashboard) +
  `api/Dockerfile.prod` (uvicorn, 2 workers, no --reload). Secrets via repo `.env` (copy from
  `.env.example`, git-ignored). `DEPLOYMENT.md` documents clone → `.env` → build → TLS via
  reverse proxy → update/backup flow. Dev stack (`docker-compose.base44.yml`) is untouched and
  stays the source-bind-mounted live-reload setup.

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
