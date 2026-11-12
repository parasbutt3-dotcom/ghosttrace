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
- No secrets in source; .env.example provided.
- Data deletion: disconnect account revokes Google token and deletes row; device deletion supported.

## Known limitations / production hardening TODO

- SQLite default; use PostgreSQL in production (docker-compose provided).
- Rate limiting via slowapi on auth, telemetry, and events creation; add nginx for prod.
- MFA (TOTP) implemented; recovery codes still TODO.
- JWT revocation list implemented for refresh tokens; access tokens expire in 24h.
- Android companion validated via Pydantic; treat as untrusted input.
- Google Workspace admin APIs partially implemented (require domain admin).
- Wazuh TLS verification configurable via WAZUH_VERIFY_SSL / WAZUH_CA_BUNDLE.

## Secrets handling

Never commit .env. Rotate SECRET_KEY and TOKEN_ENCRYPTION_KEY in production.
