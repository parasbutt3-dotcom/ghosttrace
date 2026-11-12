# Security Assessment

## Controls implemented

- OAuth 2.0 with PKCE and state validation (Google).
- Tokens encrypted at rest with Fernet (key from env).
- Passwords hashed with bcrypt.
- JWT access (24h) + refresh (30d) tokens.
- RBAC via is_admin flag.
- Audit log for auth/account/integration actions.
- Device keys stored only as SHA-256 hashes; raw key shown once.
- Input validation via Pydantic models.
- CORS allowlist from env.
- Security headers via lightweight HTTP middleware in `backend/app/main.py`: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and a strict API-oriented `Content-Security-Policy` (`default-src 'none'; frame-ancestors 'none'; base-uri 'none'`). `Strict-Transport-Security` is added only when `APP_ENV == "production"` (max-age=31536000; includeSubDomains).
- No secrets in source; .env.example provided.
- Data deletion: disconnect account revokes Google token and deletes row; device deletion supported.

## Known limitations / production hardening TODO

- SQLite default; use PostgreSQL in production (docker-compose provided).
- Rate limiting via slowapi on auth, telemetry, events, and takeout (in-memory storage today; Redis-backed storage is Phase 1.2); add nginx for prod.
- MFA (TOTP) implemented with single-use recovery codes (10 per enrolment); recovery code flow is tested.
- JWT revocation list implemented for refresh tokens; access tokens expire in 24h.
- Android companion validated via Pydantic; treat as untrusted input.
- Google Workspace admin APIs partially implemented (require domain admin).
- Wazuh TLS verification configurable via WAZUH_VERIFY_SSL / WAZUH_CA_BUNDLE.

## Token storage tradeoff (Phase 1.7)

- Access and refresh tokens are currently stored in `localStorage` on the frontend (`frontend/src/lib/auth.tsx`, `frontend/src/lib/api.ts`) and attached as `Authorization: Bearer` headers. This keeps the client simple and avoids CSRF concerns, but any XSS in the SPA can read both tokens.
- Mitigation today: strict CSP on the API responses (see above), React's default escaping, no `dangerouslySetInnerHTML` in auth paths, and short-ish access token lifetime (24h) with revocation of refresh tokens on logout/logout-all/change-password.
- Deferred (not implemented in this pass): moving refresh tokens to an `httpOnly`, `Secure`, `SameSite` cookie with server-side refresh rotation. That would remove refresh tokens from JS reach but requires changes to `backend/app/api/v1/auth.py` (set/clear cookie on login/refresh/logout) and `frontend/src/lib/api.ts` (drop localStorage refresh handling, send credentials), plus CSRF protection on cookie-authenticated mutating endpoints. Tracked as the remaining half of Phase 1.7; decision point recorded in `docs/upgrade-plan.md`.
- Revisit if/when the frontend gains third-party script or rich-text surfaces.

## Secrets handling

Never commit .env. Rotate SECRET_KEY and TOKEN_ENCRYPTION_KEY in production.
