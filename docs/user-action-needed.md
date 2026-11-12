# User Action Needed — GHOSTTRACE Phase 0.3 / 0.5

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
- [ ] Push the protected history: `git push -u origin main`.
- [ ] Open the Actions tab and confirm the first run is green.
- [ ] If CI fails, fix on a branch and re-push; do not force-push to `main`.
- [ ] (Optional, Phase 6) Add a CI badge to `README.md` once the workflow is green.

## Notes
- No `.env` values were modified by the automated agent.
- The folded `frontend/.git` scaffold history is preserved at `frontend/.git.bak/` (ignored).
