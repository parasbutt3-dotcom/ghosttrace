import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from cryptography.fernet import Fernet
from jose import JWTError, jwt

from app.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode()[:72], hashed.encode())
    except Exception:
        return False


def create_access_token(subject: str, extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": subject, "iat": now, "exp": expire, "type": "access", "jti": secrets.token_urlsafe(32)}
    if extra:
        to_encode.update(extra)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"sub": subject, "iat": now, "exp": expire, "type": "refresh", "jti": secrets.token_urlsafe(32)}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


def token_precedes_cutoff(payload: dict, user) -> bool:
    # True when the token was minted before the user's logout-all cutoff.
    # Tokens without iat (older format) are treated as stale when a cutoff exists.
    # Strict compare: iat has second granularity, so tokens re-minted within the
    # same wall-clock second as the cutoff may be rejected — they self-heal on
    # the next second and this beats leaving pre-cutoff tokens alive.
    cutoff = ensure_utc(getattr(user, "sessions_invalid_before", None))
    if cutoff is None:
        return False
    iat = payload.get("iat")
    if not iat:
        return True
    return datetime.fromtimestamp(iat, tz=timezone.utc) < cutoff


def ensure_utc(dt: datetime | None) -> datetime | None:
    # SQLite persists DATETIME without an offset, so values read back naive.
    # Treat naive values as UTC to keep comparisons with now(utc) safe.
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)


def revoke_refresh_token(db, jti: str, expires_at) -> None:
    from app.models.revoked_token import RevokedToken
    exists = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
    if not exists:
        db.add(RevokedToken(jti=jti, expires_at=expires_at))
        db.commit()


def is_token_revoked(db, jti: str) -> bool:
    from app.models.revoked_token import RevokedToken
    row = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
    if not row:
        return False
    if ensure_utc(row.expires_at) < datetime.now(timezone.utc):
        db.delete(row)
        db.commit()
        return False
    return True


def _fernet() -> Fernet:
    key = settings.TOKEN_ENCRYPTION_KEY
    if not key:
        # Derive a deterministic key from SECRET_KEY for dev only.
        digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except Exception:
        return ""


def generate_recovery_codes(count: int = 10) -> tuple[list[str], list[dict]]:
    """Return (plaintext codes for one-time display, hashed records to store)."""
    plain = [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}-{secrets.token_hex(2)}" for _ in range(count)]
    stored = [{"hash": hashlib.sha256(c.encode()).hexdigest(), "used": False} for c in plain]
    return plain, stored


def consume_recovery_code(user, code: str) -> bool:
    """True if code matches an unused recovery code; marks it used."""
    if not user.mfa_recovery_codes or not code:
        return False
    h = hashlib.sha256(code.strip().encode()).hexdigest()
    if not any(not e.get("used") and e.get("hash") == h for e in user.mfa_recovery_codes):
        return False
    # Build a fresh list (never mutate in place: SQLAlchemy compares the new value
    # against the loaded JSON and skips the UPDATE if the objects are equal).
    user.mfa_recovery_codes = [
        {**e, "used": True} if e.get("hash") == h and not e.get("used") else dict(e)
        for e in user.mfa_recovery_codes
    ]
    return True


def new_state() -> str:
    return secrets.token_urlsafe(32)


def generate_api_key() -> tuple[str, str, str]:
    """Return (full_key, sha256_hash, display_prefix)."""
    full = "gt_" + secrets.token_urlsafe(40)
    digest = hashlib.sha256(full.encode()).hexdigest()
    return full, digest, full[:10]


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def new_pkce_verifier() -> str:
    return secrets.token_urlsafe(64)


def pkce_challenge(verifier: str) -> str:
    import base64 as b64
    import hashlib as h

    digest = h.sha256(verifier.encode()).digest()
    return b64.urlsafe_b64encode(digest).rstrip(b"=").decode()
