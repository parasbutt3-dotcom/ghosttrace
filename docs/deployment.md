# Deployment Runbook — GHOSTTRACE

Production deployment guide for a single VPS (Ubuntu 22.04+). Two supported paths:
**Docker Compose** (`infra/docker-compose.prod.yml`) or **systemd + host nginx** (`infra/systemd/`,
`infra/nginx.conf`). Pick one; do not mix. Do not run Docker and the systemd units on the same
ports at the same time.

Replace `ghosttrace.example.com` and `203.0.113.10` placeholders throughout with your real
domain and server IP.

## 1. Prerequisites

- A VPS with a public IP and a domain whose DNS you control.
- Ports 80 and 443 open in the firewall (and 22 for SSH). Close 5432/6379/8000/3000 to the
  public internet — only nginx talks to them.
- For Docker path: Docker Engine 24+ and the compose plugin.
- For systemd path: Python 3.12, Node 20, PostgreSQL 16, Redis 7, nginx 1.24+, certbot.

## 2. DNS

1. Create an **A record**: `ghosttrace.example.com → 203.0.113.10`.
2. (Optional) `www.ghosttrace.example.com → 203.0.113.10` and add it to `server_name` in
   `infra/nginx.conf`.
3. Wait for propagation: `dig +short ghosttrace.example.com` must return the VPS IP.
4. Do not point the domain at the server until the certbot step (section 4) is ready, or the
   HTTP-01 challenge will fail.

## 3. Environment variables checklist

Copy `.env.example` to `/etc/ghosttrace/.env` (systemd) or `./.env` (Docker) and set every
value. Nothing below may be left as the dev default in production.

| Variable | Required | Notes |
|---|---|---|
| `APP_NAME` | no | defaults `GHOSTTRACE` |
| `APP_ENV` | yes | must be `production` |
| `DEBUG` | yes | must be `false` (gates `create_all` and debug routes) |
| `SECRET_KEY` | yes | ≥32 random chars; rotating logs everyone out |
| `DATABASE_URL` | yes | `postgresql+psycopg2://ghosttrace:<pw>@db:5432/ghosttrace` (Docker) or `...@127.0.0.1:5432/...` (systemd) |
| `REDIS_URL` | yes | `redis://redis:6379/0` (Docker) or `redis://127.0.0.1:6379/0` (systemd) |
| `ADMIN_EMAILS` | no | comma-separated bootstrap admins |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | default 1440 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | no | default 30 |
| `ALGORITHM` | no | default `HS256` |
| `TOKEN_ENCRYPTION_KEY` | yes | Fernet key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `GOOGLE_CLIENT_ID` | optional | only if Google integration enabled |
| `GOOGLE_CLIENT_SECRET` | optional | rotate per docs/user-action-needed.md 0.3 |
| `GOOGLE_REDIRECT_URI` | optional | `https://ghosttrace.example.com/api/v1/auth/google/callback` |
| `GOOGLE_SCOPES` | no | default `openid email profile` |
| `FRONTEND_URL` | yes | `https://ghosttrace.example.com` |
| `CORS_ORIGINS` | yes | `https://ghosttrace.example.com` |
| `ANDROID_API_KEY_HEADER` | no | default `X-Device-Key` |
| `EVENT_RETENTION_DAYS` | no | default 90 |
| `EMAIL_VERIFY_ENABLED` | no | `true` only if SMTP is configured |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | optional | required if email verification or digests enabled |
| `FRONTEND_VERIFY_URL` | optional | `https://ghosttrace.example.com/verify` |
| `AUTO_SYNC_ENABLED` | no | default `true` |
| `SYNC_INTERVAL_MINUTES` | no | default 60 |
| `WAZUH_VERIFY_SSL` | no | default `true`; set `false` only for self-signed Wazuh |
| `WAZUH_CA_BUNDLE` | optional | path to CA bundle when verifying |
| `POSTGRES_PASSWORD` | yes (Docker) | used by compose to provision Postgres; keep in `.env` |

Generate secrets with:
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Never commit `.env`. Only `.env.example` is tracked.

## 4. TLS certificate (certbot)

### Docker path
```bash
# 1. Bring up only nginx + certbot webroot first (or full stack with nginx).
docker compose -f infra/docker-compose.prod.yml up -d nginx
# 2. Issue the certificate via the webroot plugin.
docker compose -f infra/docker-compose.prod.yml run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d ghosttrace.example.com \
  --email you@example.com --agree-tos --no-eff-email
# 3. Start/reload nginx.
docker compose -f infra/docker-compose.prod.yml up -d
docker compose -f infra/docker-compose.prod.yml exec nginx nginx -s reload
```
Renewal runs automatically via the `certbot` service (every 12h, `certbot renew`).

### systemd path
```bash
# nginx must already be serving the challenge location from infra/nginx.conf.
sudo certbot --nginx -d ghosttrace.example.com --email you@example.com --agree-tos --no-eff-email
# or webroot:
sudo certbot certonly --webroot -w /var/www/certbot -d ghosttrace.example.com
sudo systemctl reload nginx
# enable auto-renewal timer
sudo systemctl enable --now certbot.timer
```

## 5. Deploy — Docker Compose

```bash
cd /opt/ghosttrace   # or wherever the repo lives
cp .env.example .env && $EDITOR .env
# build & push images in CI, or build locally:
docker build -t ghosttrace/backend:latest ./backend
docker build -t ghosttrace/frontend:latest ./frontend \
  --build-arg NEXT_PUBLIC_API_URL=https://ghosttrace.example.com
# run migrations before first start (optional; backend runs create_all only in dev):
docker compose -f infra/docker-compose.prod.yml run --rm backend \
  alembic -c alembic.ini upgrade head
# start
docker compose -f infra/docker-compose.prod.yml up -d
docker compose -f infra/docker-compose.prod.yml ps
```

## 6. Deploy — systemd (non-Docker)

```bash
# 1. Create user and directories.
sudo useradd --system --home /opt/ghosttrace --shell /usr/sbin/nologin ghosttrace
sudo mkdir -p /opt/ghosttrace /etc/ghosttrace /var/www/certbot
sudo chown -R ghosttrace:ghosttrace /opt/ghosttrace
# 2. Copy source.
sudo rsync -a --delete ./ /opt/ghosttrace/
# 3. Backend venv + deps.
cd /opt/ghosttrace/backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
# 4. Frontend build.
cd /opt/ghosttrace/frontend
npm ci && npm run build
# 5. Env file.
sudo cp /opt/ghosttrace/.env.example /etc/ghosttrace/.env
sudo $EDITOR /etc/ghosttrace/.env
sudo chmod 600 /etc/ghosttrace/.env
sudo chown root:ghosttrace /etc/ghosttrace/.env
# 6. Postgres + Redis (install via apt) and create role/db:
sudo -u postgres psql -c "CREATE USER ghosttrace WITH PASSWORD '...';"
sudo -u postgres psql -c "CREATE DATABASE ghosttrace OWNER ghosttrace;"
# 7. Migrations.
cd /opt/ghosttrace/backend
sudo -u ghosttrace env $(cat /etc/ghosttrace/.env | xargs) .venv/bin/alembic upgrade head
# 8. nginx site.
sudo cp /opt/ghosttrace/infra/nginx.conf /etc/nginx/nginx.conf
sudo nginx -t && sudo systemctl reload nginx
# 9. Units.
sudo cp /opt/ghosttrace/infra/systemd/*.service /opt/ghosttrace/infra/systemd/*.target /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ghosttrace.target
```

## 7. Smoke tests

Run after every deploy. All must pass.

```bash
# DNS + TLS
curl -I https://ghosttrace.example.com/health
# expect: HTTP/2 200, strict-transport-security present

# HTTP -> HTTPS redirect
curl -I http://ghosttrace.example.com/   # expect 301

# Backend readiness (DB reachable)
curl -fsS https://ghosttrace.example.com/ready   # expect {"status":"ready"}

# OpenAPI docs reachable
curl -fsS https://ghosttrace.example.com/docs >/dev/null && echo "docs ok"

# Frontend renders
curl -fsS https://ghosttrace.example.com/ | grep -q "<!DOCTYPE html" && echo "frontend ok"

# Security headers
curl -sI https://ghosttrace.example.com/api/v1/auth/login | grep -iE \
  'x-content-type-options|x-frame-options|referrer-policy|strict-transport-security|content-security-policy'

# Auth round-trip (manual): register a test account, log in, confirm /api/v1/overview returns 200.
# Rate limit sanity: 6 rapid failed logins should return 429.

# Compose health
docker compose -f infra/docker-compose.prod.yml ps   # all services "Up (healthy)" where applicable
```

## 8. Rollback

- Docker: `docker compose -f infra/docker-compose.prod.yml down` then redeploy the previous
  image tag (keep `:previous` tags). Database volume `pgdata` is preserved.
- systemd: `git checkout <previous-tag>` in `/opt/ghosttrace`, rebuild frontend, restart units:
  `sudo systemctl restart ghosttrace-backend ghosttrace-frontend`.
- Database: restore from the most recent `pg_dump` (see security-assessment retention policy).

## 9. Operations notes

- Logs: `docker compose logs -f backend` (Docker) or `journalctl -u ghosttrace-backend -f` (systemd).
- Backups: nightly `pg_dump` cron recommended (Phase 4.3); not automated by this runbook.
- Do not expose Postgres/Redis ports publicly. Only nginx (80/443) should be public.
- Keep `.env` out of version control; verify with `git ls-files | grep -x .env` (must be empty).
