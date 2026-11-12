# Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Next.js UI │────▶│  FastAPI API │────▶│  SQLite/PG   │
└─────────────┘     └──────┬───────┘     └──────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
  Google OAuth       ActivityWatch        Wazuh REST
  (OIDC tokens)      (localhost:5600)     (host:55000)
        │
        ▼
  Android companion (push telemetry via device key)
```

## Components

- Frontend: Next.js 14 App Router, Tailwind, Recharts, dark SOC theme.
- Backend: FastAPI, SQLAlchemy 2.0, Pydantic v2, JWT sessions, Fernet token encryption.
- Data: unified `events` table with dedup_key; accounts, integrations, devices, audit_logs.
- Integrations: plugin registry (`app/integrations/registry.py`) with BaseIntegration subclasses: Google (Gmail alerts / Calendar / Drive scopes), ActivityWatch, Wazuh, GitHub (public + optional PAT), Android, iOS.
- Android: push-based telemetry endpoint authenticated by hashed device key.
- Sessions: every login records a UserSession row (IP, user-agent, jti); per-session revoke plus global sign-out.
- Access: hashed API keys (`gt_…`) usable as Bearer tokens on the events API.
- Rules: user-defined detection rules evaluated in Security Center.
- Scheduler: background asyncio loop does periodic integration sync + retention cleanup.
- Insights: hour/weekday activity, top apps, streaks, cross-account correlation counts.

## Event schema

event_id, timestamp, source, account_id, device_id, application, event_type, category, description, metadata, collection_method, permission_status, confidence, dedup_key.

## Security

- OAuth tokens encrypted at rest (Fernet).
- Passwords hashed (bcrypt).
- JWT access/refresh tokens.
- RBAC (is_admin).
- Audit log.
- Device keys stored as SHA-256 hashes.
- Input validation via Pydantic.
- CORS allowlist.

## Takeout & device tooling
- `POST /api/v1/takeout/import` — parses a takeout.google.com ZIP (Location History,
  SemanticLocationHistory, My Activity JSON, YouTube history) into timeline events.
- `tools/ios_inspector.py` — reads a trusted iPhone over USB (pymobiledevice3) and pushes
  device state + battery to /devices/telemetry with the device key.
- `ios/` companion sources: TelemetryService + LocationCollector + CalendarCollector
  (permission prompts documented in ios/README.md).
