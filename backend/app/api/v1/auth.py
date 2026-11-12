import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

import logging

from app.config import settings
from app.database import get_db
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger("ghosttrace.auth")

# Prefer Redis-backed storage so rate limits survive multiple workers/processes.
# Degrade gracefully to in-memory storage when Redis is unreachable.
try:
    limiter = Limiter(key_func=get_remote_address, storage_uri=settings.REDIS_URL)
    # Limiter construction does not actually connect; verify reachability now.
    if not getattr(limiter._storage, "check", lambda: True)():
        raise RuntimeError("Redis rate-limit storage is unreachable")
except Exception as exc:
    logger.warning(
        "Redis unavailable for rate limiting; falling back to in-memory storage: %s",
        exc,
    )
    limiter = Limiter(key_func=get_remote_address)
from app.models.user import User
from app.models.oauth_state import OAuthState
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, RefreshRequest
from app.schemas.user import UserOut
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token, new_state, new_pkce_verifier, pkce_challenge, revoke_refresh_token, is_token_revoked, encrypt_secret, decrypt_secret, token_precedes_cutoff, generate_recovery_codes, consume_recovery_code
from app.schemas.auth import ChangePasswordRequest, DeleteAccountRequest
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _audit(db, user_id, action, details=None, status="success", request=None, ip=None):
    from app.models.audit import AuditLog
    if ip is None and request is not None:
        ip = getattr(request.client, "host", None) if request.client else None
    db.add(AuditLog(user_id=user_id, action=action, details=details, status=status, ip_address=ip))
    db.commit()


def _issue_tokens(db, user, request=None, mfa=False):
    """Create access+refresh tokens and record a UserSession row for the access token's jti."""
    at = create_access_token(user.id)
    rt = create_refresh_token(user.id)
    payload = decode_token(at) or {}
    jti = payload.get("jti")
    if jti:
        from app.models.session import UserSession
        ip = getattr(request.client, "host", None) if request and request.client else None
        ua = request.headers.get("user-agent") if request else None
        db.add(UserSession(user_id=user.id, jti=jti, ip_address=ip, user_agent=ua))
        db.commit()
    return TokenResponse(access_token=at, refresh_token=rt)


@router.post("/register", response_model=TokenResponse)
@limiter.limit("5/minute")
def register(req: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    is_admin = req.email.lower() in settings.admin_emails_list()
    user = User(email=req.email, hashed_password=hash_password(req.password), full_name=req.full_name, is_admin=is_admin)
    db.add(user)
    db.commit()
    db.refresh(user)
    _audit(db, user.id, "auth.register", {"email": req.email}, request=request)
    return _issue_tokens(db, user, request)


@router.post("/login")
@limiter.limit("10/minute")
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not user.hashed_password or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User inactive")
    if user.mfa_enabled:
        mfa_token = create_access_token(user.id, extra={"type": "mfa_pending"})
        return {"mfa_required": True, "mfa_token": mfa_token}
    _audit(db, user.id, "auth.login", {"email": req.email}, request=request)
    return _issue_tokens(db, user, request)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
def refresh(req: RefreshRequest, request: Request, db: Session = Depends(get_db)):
    payload = decode_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    jti = payload.get("jti")
    if jti and is_token_revoked(db, jti):
        raise HTTPException(status_code=401, detail="Token revoked")
    user = db.get(User, payload.get("sub"))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive")
    if token_precedes_cutoff(payload, user):
        raise HTTPException(status_code=401, detail="Session revoked, sign in again")
    # rotate: revoke old (keep original expiry to avoid extending lifetime)
    if jti:
        from datetime import datetime, timezone, timedelta
        exp = payload.get("exp")
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc) if exp else datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        revoke_refresh_token(db, jti, expires_at)
    new_rt = create_refresh_token(user.id)
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=new_rt,
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout")
def logout(req: RefreshRequest | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if req and req.refresh_token:
        p = decode_token(req.refresh_token)
        if p and p.get("type") == "refresh" and p.get("jti"):
            from datetime import datetime, timezone, timedelta
            revoke_refresh_token(db, p["jti"], datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))
    _audit(db, user.id, "auth.logout")
    return {"ok": True}


@router.post("/logout-all")
def logout_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Kills every token minted before now, including this session's.
    user.sessions_invalid_before = datetime.now(timezone.utc)
    db.commit()
    _audit(db, user.id, "auth.logout_all")
    return {"ok": True}


@router.post("/change-password")
@limiter.limit("5/minute")
def change_password(req: ChangePasswordRequest, request: Request,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.hashed_password or not verify_password(req.current_password, user.hashed_password):
        _audit(db, user.id, "auth.change_password", status="failed", request=request)
        raise HTTPException(status_code=401, detail="Current password incorrect")
    if req.current_password == req.new_password:
        raise HTTPException(status_code=400, detail="New password must differ")
    user.hashed_password = hash_password(req.new_password)
    # Password changed: kill all existing sessions (NIST 800-63B guidance).
    user.sessions_invalid_before = datetime.now(timezone.utc)
    db.commit()
    _audit(db, user.id, "auth.change_password", request=request)
    return {"ok": True, "note": "All sessions signed out; sign in again with the new password."}


@router.delete("/account")
@limiter.limit("5/minute")
def delete_account(req: DeleteAccountRequest, request: Request,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.hashed_password or not verify_password(req.password, user.hashed_password):
        _audit(db, user.id, "auth.account_delete", status="failed", request=request)
        raise HTTPException(status_code=401, detail="Password incorrect")
    # Best-effort OAuth revocation before wiping rows.
    from app.models.account import ConnectedAccount
    from app.core.security import decrypt_secret
    for acct in db.query(ConnectedAccount).filter(ConnectedAccount.user_id == user.id).all():
        if acct.provider == "google":
            tok = decrypt_secret(acct.access_token_enc or "") or decrypt_secret(acct.refresh_token_enc or "")
            if tok:
                try:
                    import httpx
                    httpx.post("https://oauth2.googleapis.com/revoke", params={"token": tok}, timeout=15)
                except Exception:
                    pass
    user_id = user.id
    db.delete(user)  # cascade removes accounts, integrations, devices, events, audit, oauth states
    db.commit()
    from app.models.audit import AuditLog
    db.add(AuditLog(user_id=user_id, action="auth.account_deleted", details={"note": "user self-deletion"}, status="success",
                    ip_address=getattr(request.client, "host", None) if request.client else None))
    db.commit()
    return {"ok": True, "note": "Account and all collected activity permanently deleted."}


# ---------- MFA (TOTP) ----------

@router.post("/mfa/setup")
def mfa_setup(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    import pyotp
    if user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA already enabled")
    secret = pyotp.random_base32()
    user.mfa_secret_enc = encrypt_secret(secret)
    plain, stored = generate_recovery_codes()
    user.mfa_recovery_codes = stored
    db.commit()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=user.email, issuer_name=settings.APP_NAME)
    return {"secret": secret, "otpauth_uri": uri, "recovery_codes": plain,
            "note": "Store these recovery codes safely; each works once if you lose your authenticator."}


@router.post("/mfa/verify")
def mfa_verify(code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    import pyotp
    from app.core.security import decrypt_secret
    if not user.mfa_secret_enc:
        raise HTTPException(status_code=400, detail="Run setup first")
    secret = decrypt_secret(user.mfa_secret_enc)
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid code")
    user.mfa_enabled = True
    db.commit()
    _audit(db, user.id, "auth.mfa_enabled")
    return {"ok": True, "mfa_enabled": True}


@router.post("/mfa/disable")
def mfa_disable(code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    import pyotp
    from app.core.security import decrypt_secret
    if not user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA not enabled")
    secret = decrypt_secret(user.mfa_secret_enc or "")
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid code")
    user.mfa_enabled = False
    user.mfa_secret_enc = None
    user.mfa_recovery_codes = None
    db.commit()
    _audit(db, user.id, "auth.mfa_disabled")
    return {"ok": True}


@router.post("/mfa/recovery-codes")
def mfa_recovery_codes_regenerate(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    import pyotp
    if not user.mfa_enabled or not user.mfa_secret_enc:
        raise HTTPException(status_code=400, detail="MFA not enabled")
    plain, stored = generate_recovery_codes()
    user.mfa_recovery_codes = stored
    db.commit()
    _audit(db, user.id, "auth.mfa_recovery_codes_regenerated")
    return {"recovery_codes": plain}


@router.post("/mfa/login", response_model=TokenResponse)
def mfa_login(mfa_token: str, code: str, request: Request, db: Session = Depends(get_db)):
    import pyotp
    from app.core.security import decrypt_secret
    payload = decode_token(mfa_token)
    if not payload or payload.get("type") != "mfa_pending":
        raise HTTPException(status_code=401, detail="Invalid mfa token")
    user = db.get(User, payload.get("sub"))
    if not user or not user.mfa_enabled or not user.mfa_secret_enc:
        raise HTTPException(status_code=401, detail="MFA not configured")
    if token_precedes_cutoff(payload, user):
        raise HTTPException(status_code=401, detail="Session revoked, sign in again")
    secret = decrypt_secret(user.mfa_secret_enc)
    totp = pyotp.TOTP(secret)
    used_recovery = False
    if not totp.verify(code, valid_window=1):
        # Fallback: single-use recovery code
        if not consume_recovery_code(user, code):
            raise HTTPException(status_code=401, detail="Invalid code")
        used_recovery = True
        db.commit()
    _audit(db, user.id, "auth.login", {"mfa": True, "recovery_code": used_recovery})
    return _issue_tokens(db, user, request)


# ---------- Sessions ----------

@router.get("/sessions")
def list_sessions(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models.session import UserSession
    from app.core.security import ensure_utc
    current_jti = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        p = decode_token(auth_header[7:].strip())
        current_jti = (p or {}).get("jti")
    rows = db.query(UserSession).filter(UserSession.user_id == user.id).order_by(UserSession.created_at.desc()).limit(50).all()
    out = []
    for s in rows:
        created = ensure_utc(s.created_at)
        out.append({
            "id": s.id, "ip_address": s.ip_address, "user_agent": s.user_agent,
            "created_at": created.isoformat() if created else None,
            "last_seen_at": ensure_utc(s.last_seen_at).isoformat() if s.last_seen_at else None,
            "current": bool(current_jti) and s.jti == current_jti,
            "revoked": s.revoked,
        })
    return {"sessions": out}


@router.post("/sessions/{session_id}/revoke")
def revoke_session(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models.session import UserSession
    sess = db.query(UserSession).filter(UserSession.id == session_id, UserSession.user_id == user.id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="not found")
    sess.revoked = True
    db.commit()
    _audit(db, user.id, "auth.session_revoked", {"session_id": session_id})
    return {"ok": True}


# ---------- Google OAuth ----------

import logging
from urllib.parse import urlencode

logger = logging.getLogger("ghosttrace.auth.google")


@router.get("/google/login")
def google_login(include_gmail: bool = False, include_calendar: bool = False, include_drive: bool = False,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google OAuth not configured (set GOOGLE_CLIENT_ID/SECRET)")
    # Drop stale/unconsumed states for this user so the table can't accumulate.
    db.query(OAuthState).filter(
        OAuthState.user_id == user.id,
        OAuthState.provider == "google",
    ).delete()
    state = new_state()
    verifier = new_pkce_verifier()
    challenge = pkce_challenge(verifier)
    scopes = settings.GOOGLE_SCOPES
    if include_gmail:
        scopes += " https://www.googleapis.com/auth/gmail.readonly"
    if include_calendar:
        scopes += " https://www.googleapis.com/auth/calendar.readonly"
    if include_drive:
        scopes += " https://www.googleapis.com/auth/drive.readonly"
    os_row = OAuthState(user_id=user.id, provider="google", state=state, code_verifier=verifier,
                        redirect_uri=settings.GOOGLE_REDIRECT_URI, extra={"requested_scopes": scopes})
    db.add(os_row)
    db.commit()

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": scopes,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return {"authorization_url": url, "state": state}


@router.get("/google/callback")
def google_callback(code: str | None = None, state: str | None = None, error: str | None = None, db: Session = Depends(get_db)):
    import httpx
    from datetime import timedelta
    from app.core.security import encrypt_secret, ensure_utc
    from app.models.account import ConnectedAccount
    from app.models.integration import Integration

    def _fail(reason: str, user_id: str | None = None, detail: str | None = None) -> RedirectResponse:
        # Log the real cause server-side; only a safe slug reaches the client.
        logger.warning("google callback failed: %s (user=%s): %s", reason, user_id, detail or "")
        if user_id:
            _audit(db, user_id, "auth.google_connect_failed", {"reason": reason}, status="failed")
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/integrations?error={reason}")

    if error:
        # Google's error param is attacker-influenced; only pass known slugs through.
        reason = error if error in {"access_denied", "consent_required", "login_required", "selection_required", "immediate_failed"} else "google_error"
        return _fail(reason)
    if not code or not state:
        return _fail("missing_code_or_state")

    os_row = db.query(OAuthState).filter(OAuthState.state == state).first()
    if not os_row or ensure_utc(os_row.expires_at) < datetime.now(timezone.utc):
        return _fail("invalid_or_expired_state")
    user_id = os_row.user_id
    verifier = os_row.code_verifier
    # The auth code and state are both single-use: consume the state row up front,
    # even if the exchange below fails, to close the replay window.
    db.delete(os_row)
    db.commit()

    user = db.get(User, user_id) if user_id else None
    if not user:
        return _fail("no_user_for_state")

    # Exchange code for tokens
    try:
        token_resp = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            },
            timeout=30,
        )
    except httpx.HTTPError as e:
        return _fail("token_exchange_unreachable", user.id, str(e))
    if token_resp.status_code != 200:
        return _fail("token_exchange_failed", user.id, token_resp.text)
    tok = token_resp.json()
    access_token = tok.get("access_token")
    refresh_token = tok.get("refresh_token")
    # Google returns expires_in as a string ("3600") — normalize before timedelta.
    try:
        expires_in = int(tok.get("expires_in", 3600))
    except (TypeError, ValueError):
        expires_in = 3600
    scopes = tok.get("scope", settings.GOOGLE_SCOPES).split()
    if not access_token:
        return _fail("token_exchange_failed", user.id, "no access_token in response")

    # Get user info
    userinfo = {}
    try:
        ui = httpx.get("https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": f"Bearer {access_token}"}, timeout=30)
        if ui.status_code == 200:
            userinfo = ui.json()
    except httpx.HTTPError as e:
        logger.warning("google userinfo fetch failed: %s", e)

    sub = userinfo.get("sub")
    if sub:
        # Cross-link guard: one Google identity must map to one Ghosttrace user.
        other = db.query(ConnectedAccount).filter(
            ConnectedAccount.provider == "google",
            ConnectedAccount.provider_account_id == sub,
            ConnectedAccount.user_id != user.id,
        ).first()
        if other:
            return _fail("account_already_linked", user.id, "google sub linked to another user")

    acct = db.query(ConnectedAccount).filter(
        ConnectedAccount.user_id == user.id, ConnectedAccount.provider == "google"
    ).first()
    if not acct:
        acct = ConnectedAccount(user_id=user.id, provider="google")
        db.add(acct)
    if sub:
        acct.provider_account_id = sub
        acct.display_name = userinfo.get("name")
        acct.email = userinfo.get("email")
    acct.scopes = scopes
    acct.access_token_enc = encrypt_secret(access_token)
    if refresh_token:
        acct.refresh_token_enc = encrypt_secret(refresh_token)
    acct.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    acct.status = "connected"
    if userinfo:
        acct.metadata_json = {"userinfo": userinfo}
    # Assign the account PK before linking it to the integration row;
    # without this, a newly created acct.id would still be None here.
    db.flush()

    # create integration row
    integ = db.query(Integration).filter(Integration.user_id == user.id, Integration.kind == "google").first()
    if not integ:
        integ = Integration(user_id=user.id, account_id=acct.id, kind="google", name="Google Account")
        db.add(integ)
    else:
        integ.account_id = acct.id
        integ.status = "idle"

    db.commit()

    _audit(db, user.id, "auth.google_connected", {"email": userinfo.get("email") or user.email, "scopes": scopes})
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/integrations?connected=google")
