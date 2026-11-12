# User Action Needed — GHOSTTRACE (Phase 0.3, 0.5, 1.7, 2.9, 3.4, 4.1/4.6)

These items from `docs/upgrade-plan.md` Phase 0 require account/console access that only the
repository owner can perform. They were **not** done by the automated agent, and no `.env`
values were changed.

## 0.3 — Rotate the Google OAuth secret (security)

The current `.env` contains live `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` values. Because
the repo is now under git, those values must never be committed (`.gitignore` ignores `.env`,
and only `.env.example` is tracked). Rotate the secret so any leaked copy is dead.

Checklist:
- [ ] Open Google Cloud Console → APIs & Services → Credentials.
- [ ] Locate the OAuth 2.0 Client ID used by GHOSTTRACE (compare `GOOGLE_CLIENT_ID` in `.env`).
- [ ] Click "Reset secret" (or delete + recreate the client) to invalidate the old secret.
- [ ] Copy the new client secret.
- [ ] Update `.env` locally: set `GOOGLE_CLIENT_SECRET=<new value>` (do **not** commit `.env`).
- [ ] Re-test the Google connect flow (`/api/v1/auth/google/...`) end to end.
- [ ] If the old secret ever appeared in git history, history has already been purged because
      the root repo was initialized fresh (only `.env.example` is tracked) — verify with
      `git ls-files | grep -x .env` (must be empty).
- [ ] Confirm no credentials remain tracked: `git grep -n "GOOGLE_CLIENT_SECRET" $(git rev-list --all)`.

## 0.5 — Add a private GitHub remote and push (makes CI run)

`.github/workflows/ci.yml` exists but has never executed. Pushing to GitHub is the only way to
run backend pytest, frontend lint+build, and the iOS swiftc typecheck.

Checklist:
- [ ] Create a **private** repository on GitHub (e.g. `parasbutt3-dotcom/ghosttrace`).
- [ ] Add the remote: `git remote add origin git@github.com:<owner>/ghosttrace.git`
      (or HTTPS with a PAT).
- [ ] Push the protected history: `git push -u origin main` (then `git push --tags`).
- [ ] Open the Actions tab and confirm the first run is green.
- [ ] If CI fails, fix on a branch and re-push; do not force-push to `main`.
- [ ] (Optional, Phase 6) Add a CI badge to `README.md` once the workflow is green.

## 3.4 — Configure an alert delivery provider (SMTP / webhook)
Alert delivery (email + webhook) ships in code but email is a no-op unless SMTP is
configured; webhooks are per-user URLs set in the app.

Checklist:
- [ ] Choose an email path: personal SMTP, Resend, or Apprise (see
      `backend/app/services/notifications.py`).
- [ ] Set in `.env`: `EMAIL_VERIFY_ENABLED=true`, `SMTP_HOST`, `SMTP_PORT`,
      `SMTP_USER`, `SMTP_PASSWORD`, `FRONTEND_VERIFY_URL` (for verification links).
- [ ] Re-test: trigger a detection rule and confirm an email + webhook land.
- [ ] (Optional) Leave email disabled; webhook-only delivery still works.

## 4.1 / 4.6 — Choose a deployment target and production secrets
`infra/` now ships a hardened compose stack (nginx + certbot), systemd units,
backup/restore scripts and APScheduler. Pick one deployment path and provision
secrets; do not straddle VPS and PaaS.

Checklist:
- [ ] Decide target: own VPS (use `infra/docker-compose.prod.yml` + `infra/nginx.conf`)
      or PaaS (Fly.io). Documented in `docs/deployment.md`.
- [ ] Generate production `SECRET_KEY` (>=32 chars) and `TOKEN_ENCRYPTION_KEY`
      (Fernet). Store via docker secrets or a vaulted env — never commit.
- [ ] Set `APP_ENV=production`, `DEBUG=false`, `DATABASE_URL` (Postgres),
      `REDIS_URL`, `AUTO_SYNC_ENABLED` as desired.
- [ ] Configure `SENTRY_DSN` if using observability (`backend/app/metrics.py`).
- [ ] Run a restore drill with `infra/restore.sh` before relying on backups.
- [ ] Rotate `SECRET_KEY` + `TOKEN_ENCRYPTION_KEY` on any suspected leak
      (security-assessment documents the procedure).

## 2.9 — iOS Screen Time entitlement (paid, approval-gated)
iOS reports `screen_time` and `motion_activity` as `available: false` with a
reason until the Family Controls entitlement is granted and CoreMotion is wired.
This is a product decision; default is off at zero cost.

Checklist:
- [ ] Decide: implement Screen Time (requires Apple Developer Program +
      Family Controls entitlement approval) or keep capability honestly off.
- [ ] If implementing: enroll, request the entitlement, wire CoreMotion in
      `ios/TelemetryService.swift`, flip the capability flag + reason, and
      update `backend/tests/test_capabilities.py`.
- [ ] If keeping off: no action; the flag stays false (current state).

## 1.7 — Refresh-token storage (optional hardening)
Refresh tokens currently live in `localStorage` (XSS-exposed) with a JS refresh
interceptor. An httpOnly-cookie path is the documented future hardening item.

Checklist:
- [ ] Decide: keep localStorage (current, simple) or move refresh to an
      httpOnly cookie (touches `backend/app/api/v1/auth.py` + `frontend/src/lib/api.ts`).
- [ ] If moving: implement cookie set/clear on login/refresh/logout and update
      tests; document the tradeoff in `docs/security-assessment.md`.

## Notes
- No `.env` values were modified by the automated agent.
- The folded `frontend/.git` scaffold history is preserved at `frontend/.git.bak/` (ignored).
- New sections above (3.4, 4.1/4.6, 2.9, 1.7) were added in the Phase 6
  release pass to capture outstanding owner-only steps surfaced by the upgrade.
