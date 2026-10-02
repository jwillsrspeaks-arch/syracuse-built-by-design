# Deploying BUILT BY DESIGN to a public server

The app is two containers: an nginx web frontend (serves `index.html` and
`dashboard.html`, proxies `/api/*`) and a FastAPI capture backend storing
sessions in SQLite on a Docker volume (`api-data` → `/data/assessment.db`).

## 1. Get the code on the server

```bash
git clone <your-repo-url> built-by-design
cd built-by-design
```

## 2. Configure secrets

```bash
cp .env.example .env
```

Fill in:

- `DASHBOARD_PASSWORD` — required. Long random string; protects `/dashboard`
  and the invite management endpoints.
- `GOOGLE_APPS_SCRIPT_URL` / `GOOGLE_APPS_SCRIPT_TOKEN` — optional; enables
  the "Export to Sheets" button. Both come from the Apps Script you deployed
  from your own Google Sheet (the token must also be pasted into the script's
  `TOKEN` line). Leave blank to disable the export.
- `WEB_PORT` — set only if port 80 is taken by another proxy on the host.

`.env` is git-ignored — never commit it.

## 3. Build and run

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Verify:

```bash
curl -s http://localhost/ | head -3          # page doctype
curl -s http://localhost/api/healthz          # {"ok": true, ...}
```

## 4. HTTPS

The web container speaks plain HTTP on port 80; terminate TLS in front of it.
Easiest is Caddy on the same host:

```
your-domain.com {
    reverse_proxy localhost:8080   # with WEB_PORT=8080 in .env
}
```

or nginx + certbot. Point DNS at the server, issue the certificate, done —
the app is origin-agnostic (nginx `server_name _`).

## 5. Updating

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Sessions live in the `api-data` volume and survive rebuilds and container
removal. Back it up like a database file:

```bash
docker run --rm -v built-by-design_api-data:/data -v $PWD:/backup alpine \
  cp /data/assessment.db /backup/
```

## Notes

- Production images bake the source at build time (unlike the dev setup, which
  bind-mounts it); every deploy is a rebuild.
- The API runs 2 uvicorn workers; SQLite writes are serialized per file, which
  is fine at this app's scale. If you ever need more, move to Postgres first.
- Dashboard keys and invite keys are created in the dashboard UI after deploy;
  invite links should use your public domain (`https://your-domain.com/?key=BBD-XXXXXX`).
