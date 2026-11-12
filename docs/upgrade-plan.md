# GHOSTTRACE — Upgrade Plan

Source: 2026-11-13 audit. Verified state at plan time: backend 19/19 pytest passing, frontend lint+build clean, all 13 routes build. Root is NOT a git repository; only `frontend/.git` exists with a single Create-Next-App commit and all real work untracked.

Guiding order: protect the asset → make it truthful → make the companions real → make it usable → make it deployable → make it provable.

---

## Phase 0 — Asset protection (do first, ~half a day)

Everything else is at risk until this is done.

| # | Task | Detail | Acceptance |
|---|------|--------|------------|
| 0.1 | Git-init the project root | `git init` at repo root; import `frontend/.git` history (or fold frontend into root repo, keeping its single initial commit as a tag). One repo for backend + frontend + mobile + docs + site. | `git log` shows history; `git status` clean |
| 0.2 | Root `.gitignore` | Must cover: `.env`, `*.db` (ghosttrace.db, test_ghosttrace.db, debug_rc.db), `node_modules/`, `.next/`, `__pycache__/`, `*.log`, `.pytest_cache/`, `android/.gradle/`, `ios/build/` | No secrets or junk in `git ls-files` |
| 0.3 | Rotate the Google OAuth secret | `GOOGLE_CLIENT_ID/SECRET` are live values in `.env`. Rotate in Google Cloud Console, purge the old value from any history before first commit (commit only `.env.example`). | Old secret dead; repo contains no credentials |
| 0.4 | Add `LICENSE` (MIT) | README claims MIT; file only exists in the old landing-page draft. | File at root |
| 0.5 | Push to a private GitHub remote | Makes `.github/workflows/ci.yml` (backend pytest, frontend lint+build, iOS swiftc typecheck) actually run for the first time. | CI green on first push |

**Cleanup inside 0.2:** delete stray `backend/debug_rc.db`, `backend/uvicorn.log`, root `*.db` duplicates (root and backend/ both hold copies), `frontend/frontend-dev.log`.

---

## Phase 1 — Correctness & honesty (week 1)

The core is working but several claims don't match reality. Fix the truth layer before adding features.

| # | Task | Problem today | Acceptance |
|---|------|---------------|------------|
| 1.1 | Real Alembic migrations | `0001_initial.py` wraps `Base.metadata.create_all` — fine greenfield, useless for evolving an existing DB; and `main.py` still calls `create_all` on import, which bypasses Alembic entirely. | Hand-written schema migrations; `create_all` gated to DEBUG/dev only; test runs `alembic upgrade head` from empty |
| 1.2 | Redis-backed rate limiting + revocation | slowapi runs with default in-memory storage; `RevokedToken` exists but multi-worker/multi-process state diverges. Redis is already in compose but **unused by code**. | `storage_uri=REDIS_URL`; state survives `uvicorn --workers N` |
| 1.3 | Align capability flags to reality | iOS `capabilities()` claims `screen_time: True` and `motion_activity: True`, but ios/README admits the Family Controls entitlement isn't enabled and no CoreMotion code exists. Android claims `app_usage_stats: True` while the companion sends an empty events array. | Flags report `available: false` with honest `reason` until the code exists; add a backend test asserting flags ⇄ implementation parity |
| 1.4 | Update stale docs | security-assessment.md still lists recovery codes as TODO (implemented, tested); architecture.md says Next.js 14 (actual 16.4.6); installation.md drift. | Docs match code; changelog note |
| 1.5 | Rule edit UI | Backend has `PATCH /rules/{id}`; frontend `rulesApi` only lists/creates/deletes — no edit, no enable/disable toggle in `security/page.tsx`. | Edit + toggle in Security Center, covered by one vitest case |
| 1.6 | Email verification at registration | `POST /register` returns live tokens immediately — anonymous anyone can sign up and the platform never confirms ownership. | Verification link/OTP flow; unverified accounts get a restricted state; rate limit already in place |
| 1.7 | Security headers + token storage review | Only CORS middleware exists. No CSP/HSTS/X-Frame-Options. Tokens live in `localStorage` (XSS-exposed) — at minimum add an httpOnly cookie path for refresh, or document the tradeoff. | `sse-starlette`/middleware adding headers; Lighthouse/observatory pass |

---

## Phase 2 — Make the mobile companions real (weeks 2–3)

Currently: Android is a hardcoded stub (`battery=80`, `network_type="wifi"`, empty events, per `TelemetryWorker.kt`), iOS is drop-in sources with no project file.

### Android (2.1–2.6)
| # | Task |
|---|------|
| 2.1 | Full Gradle project: `gradlew`, version catalog, `app/build.gradle.kts` wired to real sources (some gradle files exist but nothing builds today) |
| 2.2 | Real device data: `BatteryManager`, `ConnectivityManager`, `Build` fields replacing the hardcoded values |
| 2.3 | Usage-stats collection: `UsageStatsManager` queries on a WorkManager periodic job → `app.usage` events (PACKAGE_USAGE_STATS flow already documented in android/README.md) |
| 2.4 | Location (optional, runtime-permission-gated) → `location.point` events; matches the consent language already in the README |
| 2.5 | `device_key` stored in Android Keystore; first-run consent screen; visible "tracking active" notification (no-stealth rule from the README, made literal) |
| 2.6 | CI: `assembleDebug` on ubuntu runner + `adb` smoke test; APK attached to releases |

### iOS (2.7–2.10)
| # | Task |
|---|------|
| 2.7 | Actual Xcode project (`project.pbxproj`, signing config) wrapping the three existing collectors |
| 2.8 | Real battery/network via UIKit (currently only partially wired in TelemetryService.swift), background modes per Info.plist keys already documented |
| 2.9 | Screen Time: implement *or* keep the capability flag honestly false (see 1.3). Family Controls entitlement is a paid-program decision — flag as user choice, default: off with reason |
| 2.10 | Reuse `tools/ios_inspector.py` (pymobiledevice3 USB fallback) as the no-app-install path: document it in ios/README, add a `--dry-run` mode |

---

## Phase 3 — Product features (weeks 3–5)

The data is already there (`location.point`, `calendar.event`, `drive.file_modified`, `git.*`, alerts); the UI doesn't surface it yet.

| # | Feature | Notes |
|---|---------|-------|
| 3.1 | **Map view** on timeline — takeout + device + iOS location events already carry lat/lon; render with react-simple-maps or maplibre (lazy-loaded) |
| 3.2 | **Event detail drawer** — metadata JSON is ingested and stored but never shown; add expand-on-click in timeline |
| 3.3 | **Cross-source search** — timeline search exists server-side (`q` param); add saved queries + filter chips for source/category/date |
| 3.4 | **Alert delivery** — detection rules currently only surface when someone opens Security Center. Add email (SMTP) + webhook notifications, and an acknowledged-state on alerts (new column + migration via 1.1) |
| 3.5 | **Scheduled weekly digest** — reports/summary endpoint already computes it; scheduler loop (services/scheduler.py) just needs a "email if SMTP configured" branch |
| 3.6 | **Integrations UX** — show last sync summary per integration (syncs already return rich dicts; persist the last summary), one-click "Sync now" already works via `POST /{id}/sync`, add progress state |
| 3.7 | **API docs surface** — FastAPI /docs exists; add a settings-page "API keys + curl examples" guide so the `gt_` keys feel finished |

---

## Phase 4 — Production readiness (weeks 5–6)

| # | Task | Detail |
|---|------|--------|
| 4.1 | Deployment target | `infra/` is empty. Ship either a hardened compose stack (nginx + certbot sidecar) or a small VPS/systemd + nginx guide. Pick one, don't straddle. |
| 4.2 | Postgres by default | SQLite is still the default path (`.env` + config default). Document + test the PG path (compose already defines it); `psycopg2` is in requirements — add `asyncpg` only if going async DB later |
| 4.3 | Backup story | nightly `pg_dump` cron + restore drill documented in installation.md; retention config exists (90d), backups are the missing mirror of it |
| 4.4 | Real scheduler | Replace asyncio in-process loop with APScheduler (single dependency, matches current style) or Celery only if 4.x worker fan-out is actually needed; the loop docstring already flags this |
| 4.5 | Observability | `/ready` health exists; add Prometheus `/metrics` (event counts, sync errors, scheduler lag) + Sentry/GlitchTip SDK behind an env flag |
| 4.6 | Secrets at deploy | env-file is fine for dev; use docker secrets or a vaulted env on server; document rotation of SECRET_KEY + TOKEN_ENCRYPTION_KEY (security-assessment already says this) |

---

## Phase 5 — Test & quality net (runs parallel from week 2)

| # | Task | Today |
|---|------|-------|
| 5.1 | Backend: tests for ActivityWatch + Wazuh syncs (zero coverage today; GitHub/Google already have mocked tests) | 19 passing tests |
| 5.2 | Backend: ruff + mypy in CI, no-`any` policy for new code | no type/lint CI |
| 5.3 | Frontend: vitest + testing-library — auth flow, MFA page, integrations connect/disconnect | zero tests |
| 5.4 | E2E: Playwright against `docker compose up` — register → connect ActivityWatch mock → event appears on timeline | none |
| 5.5 | Ingest load test: k6 against `/events` + `/devices/telemetry` to validate the new rate limits at ~1k devices | none |

---

## Phase 6 — Polish & release (weeks 7–8)

1. Landing site (already deployed via ZCode Sites, `ghosttrace-58vd`): add docs links, hosted screenshots, honest "what data we can't get" section (the capability-gap feature is the differentiator — sell it).
2. `v0.1.0` git tags for this state, then semver toward 1.0.0.
3. CHANGELOG.md from the phase list above.
4. README: CI badge (live after Phase 0.5), single-command quickstart (`docker compose up` → register → connect).
5. Attribution page: research-report.md content surfaced publicly (MIT + API-only integration claims need the receipts).

---

## Dependency graph

```
Phase 0 (git/secret) ──► everything below (safe history)
1.1 real migrations ──► 3.4 alert state, 4.x prod schema
1.3 honest capabilities ──► 2.9 Screen Time decision
2.x companions ──► 5.5 load test ──► 4.x production
Phase 5 tests ride along with 1–4
```

## Decision points needing the user

1. **iOS Screen Time** — requires Apple Developer + Family Controls entitlement (paid, approval-gated). Implement or keep capability honestly off? (default: off, cost is zero)
2. **Refresh-token storage** — localStorage + JS refresh interceptor (current, simple) vs httpOnly cookie + server-side refresh (safer, touches auth.py + api.ts). (default: cookie refresh in 1.7)
3. **Deployment target** — own VPS nginx/compose vs PaaS (Fly.io). Affects 4.1 effort by ~2 days.
4. **Alert email provider** — personal SMTP/Resend/Apprise. Needed before 3.4 ships.

## Suggested sequencing summary

- **Week 0:** Phase 0 (half day) + 1.1–1.4
- **Week 1–2:** 1.5–1.7, start 2.1–2.4 Android, 5.1 backend tests
- **Week 2–3:** finish 2.5–2.10 iOS
- **Week 3–5:** Phase 3 features, one per ~2 days
- **Week 5–6:** Phase 4, cut over to Postgres + nginx
- **Week 7–8:** Phase 6 release. Realistic total: **~8 weeks part-time / ~5 weeks full-time solo.**
