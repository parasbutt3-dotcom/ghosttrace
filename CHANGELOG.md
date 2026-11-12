# Changelog

All notable changes to GHOSTTRACE are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-11-13

First tagged release. Combines the original 0.1.0 baseline (auth, integrations,
timeline, security center, reports) with the upgrade pass (Phases 0–5 of
`docs/upgrade-plan.md`).

### Added

- **Asset protection (Phase 0):** project-root git repository, root `.gitignore`,
  MIT `LICENSE`, and a `docs/user-action-needed.md` checklist for the
  owner-only console steps.
- **Real Alembic migrations (Phase 1.1):** consolidated `0001_initial` schema
  migration; `Base.metadata.create_all` gated to dev/DEBUG; added
  `0002_email_verification` and `0003_alert_ack` migrations.
- **Redis-backed rate limiting (Phase 1.2):** slowapi storage now uses
  `REDIS_URL`; revoked-token state is shared across workers.
- **Honest capability flags (Phase 1.3):** iOS reports `screen_time`,
  `motion_activity`, `health_data` as unavailable with reasons; Android reports
  `app_usage_stats` as unavailable; parity test in
  `backend/tests/test_capabilities.py`.
- **Email verification (Phase 1.6):** optional SMTP verification flow
  (`EMAIL_VERIFY_ENABLED`, `SMTP_*`), restricted unverified state, migration.
- **Security headers (Phase 1.7):** CSP, HSTS, X-Frame-Options and related
  middleware in `backend/app/main.py`.
- **Rule edit UI (Phase 1.5):** edit + enable/disable toggle in Security Center
  backed by `PATCH /rules/{id}`.
- **Mobile companions (Phase 2):** buildable Android Gradle project with real
  battery/network/OS data, UsageStats collection, optional location,
  Keystore-backed device key, consent screen and tracking notification; iOS
  project sources (`project.yml`, app entry, TelemetryService, SettingsView)
  with real battery/network and background modes; `tools/ios_inspector.py`
  `--dry-run`.
- **Timeline map view (Phase 3.1):** lazy-loaded `LocationMap` for
  location-carrying events.
- **Event detail drawer (Phase 3.2):** expand-on-click metadata in the
  timeline.
- **Cross-source search (Phase 3.3):** saved queries and filter chips on the
  timeline.
- **Alert delivery (Phase 3.4):** email (SMTP) + webhook notifications with
  24 h rate limiting and an acknowledged/dismissed state on alerts
  (`alert_ack` table, migration `0003_alert_ack`).
- **Sync summaries (Phase 3.6):** per-integration last sync summary persisted
  and shown; progress state; one-click "Sync now".
- **API guide (Phase 3.7):** settings-page API keys + curl examples.
- **Deployment stack (Phase 4.1–4.4):** production compose, nginx, systemd
  units, backup/restore scripts, APScheduler-based scheduler, Prometheus
  `/metrics`, optional Sentry.
- **Tests (Phase 5):** backend suite now 32 tests (incl. contract tests for
  ActivityWatch/Wazuh, capabilities, email verification); frontend vitest suite
  (20 tests) covering auth, MFA, integrations, timeline; Playwright E2E smoke;
  ruff + mypy in CI.

### Changed

- Docs aligned to code: `architecture.md` (Next.js 16), `security-assessment.md`
  (recovery codes implemented), `installation.md`/`deployment.md` (Postgres path).
- `README.md` quickstart and CI badge placeholder.
- Landing site (`site/index.html`) feature set and honest-capabilities section.

### Fixed

- Capability flags no longer over-claim unimplemented collection paths.
- Rate limiter and revoked-token state consistent across processes via Redis.

### Security

- Rotated-secret guidance and `.env` exclusion documented; no credentials
  committed (`.env` gitignored, only `.env.example` tracked).
- Security headers added; token storage tradeoff documented.

### Known limitations / user action required

- Google OAuth secret rotation, GitHub remote push, SMTP provider, deployment
  target, and iOS Screen Time entitlement are owner-only steps; see
  `docs/user-action-needed.md`.
- iOS Screen Time and Android usage-stats collection remain honestly disabled
  until the respective entitlements/code are added.
- Refresh tokens are still stored in `localStorage`; httpOnly-cookie path is a
  documented future hardening item.

[0.1.0]: https://github.com/YOUR_USERNAME/ghosttrace/releases/tag/v0.1.0