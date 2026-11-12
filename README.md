# GHOSTTRACE

[![CI](https://github.com/YOUR_USERNAME/ghosttrace/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/ghosttrace/actions/workflows/ci.yml)

Open-Source Intelligence & Activity Monitoring Platform.

Personal security-operations-style dashboard that aggregates activity from authorized sources: Google account (OAuth), ActivityWatch, Wazuh, and an optional Android companion. Never fabricates events; reports unavailable data honestly.

## Stack

- Frontend: Next.js 16, TypeScript, Tailwind, Recharts
- Backend: FastAPI, SQLAlchemy, PostgreSQL/SQLite, JWT, Fernet encryption
- Integrations: plugin registry (Google, ActivityWatch, Wazuh, Android, extensible)

## Quick start

One command with Docker Compose (Postgres + Redis + backend + frontend):

```bash
git clone https://github.com/YOUR_USERNAME/ghosttrace
cd ghosttrace
cp .env.example .env
# fill in SECRET_KEY / TOKEN_ENCRYPTION_KEY (and optional Google OAuth) in .env
docker compose up --build
```

Then open http://localhost:3000, register an account, and connect your sources.

SQLite-only dev path: see `docs/installation.md`.

## Documentation

- docs/research-report.md
- docs/architecture.md
- docs/security-assessment.md
- docs/installation.md
- docs/deployment.md
- docs/upgrade-plan.md
- CHANGELOG.md
## License

MIT (original code). Integrations use upstream projects' APIs only; see research-report.md for attribution.