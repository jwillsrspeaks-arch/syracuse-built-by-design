# Deploying BUILT BY DESIGN to a public server

The app is two containers: an nginx web frontend (serves `index.html` and
`dashboard.html`, proxies `/api/*`) and a FastAPI capture backend storing
sessions in SQLite on a Docker volume (`api-data` → `/data/assessment.db`).

## 0. Provision the droplet (DigitalOcean or Hetzner)

Both providers work identically once you have an Ubuntu 24.04 box with Docker —
the only difference is where you create it:

- **DigitalOcean** (from ~$6/mo): Create → Droplets → Region `tor1`/`nyc1` →
  Image **Ubuntu 24.04 LTS** → Basic plan, Regular SSD → **1 GB / 1 vCPU** is plenty
  for a 100-user assessment tool → add your SSH key → create.
- **Hetzner** (from ~€4.50/mo): New project → Add Server → Location `fsn1`/`ash` →
  Image **Ubuntu 24.04** → **CX22 (2 vCPU)** → SSH key → create.

Then, in a terminal with your SSH key loaded:

```bash
ssh root@<DROPLET_IP>

# install Docker (same commands on both providers)
curl -fsSL https://get.docker.com | sh

# open the right ports (ufw is preinstalled on Ubuntu; allow SSH first!)
ufw allow OpenSSH && ufw allow 80,443/tcp && ufw --force enable
```

**DNS:** in your domain's DNS settings, add an `A` record pointing
`your-domain.com` (or `assess.your-domain.com`) at the droplet's IPv4 address.
Wait for it to resolve (`dig +short your-domain.com`) before issuing certificates.

The rest of this guide runs on that droplet.

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
Easiest is Caddy on the droplet itself (auto-renewing certificates, zero config
beyond the domain):

```bash
# set WEB_PORT=8080 in .env first, then: docker compose -f docker-compose.prod.yml up -d --build
apt install -y caddy

cat > /etc/caddy/Caddyfile <<'EOF'
your-domain.com {
    reverse_proxy localhost:8080
}
EOF

systemctl reload caddy
```

Caddy fetches and renews the Let's Encrypt certificate automatically as long as
DNS points at the droplet and ports 80/443 are open. (Alternative: nginx +
certbot — same result, more steps.) The app is origin-agnostic
(nginx `server_name _`), so the domain just needs DNS + the proxy.

## 5. Updating

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Sessions live in the `api-data` volume and survive rebuilds and container
removal. Back it up like a database file (copy it off the droplet too —
`scp root@<DROPLET_IP>:/root/built-by-design/assessment.db.backup .`):

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
