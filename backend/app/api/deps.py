from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token, hash_api_key, token_precedes_cutoff
from app.database import get_db
from app.models.user import User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
    request: Request = None,  # type: ignore[assignment]
) -> User:
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(creds.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.get(User, payload.get("sub"))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    if token_precedes_cutoff(payload, user):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session revoked, sign in again")
    # Per-session control: a revoked login (by jti) kills that access token too.
    jti = payload.get("jti")
    if jti:
        from app.models.session import UserSession
        sess = db.query(UserSession).filter(UserSession.jti == jti).first()
        if sess and sess.revoked:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session revoked, sign in again")
        # Keep last_seen fresh without writing on every single request:
        # touch only if it's been > 60s since the last update.
        if sess:
            now = datetime.now(timezone.utc)
            seen = sess.last_seen_at
            if seen is not None and seen.tzinfo is None:
                seen = seen.replace(tzinfo=timezone.utc)
            if seen is None or (now - seen).total_seconds() > 60:
                sess.last_seen_at = now
                db.commit()
    return user


def get_current_user_or_api_key(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    """Accepts either a JWT access token or an `gt_` API key in the Authorization header."""
    token = creds.credentials if creds else request.headers.get("Authorization", "").replace("Bearer ", "")
    if token.startswith("gt_"):
        from app.models.apikey import ApiKey
        ak = db.query(ApiKey).filter(ApiKey.key_hash == hash_api_key(token)).first()
        if not ak:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        user = db.get(User, ak.user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
        ak.last_used_at = datetime.now(timezone.utc)
        db.commit()
        return user
    return get_current_user(creds=creds, db=db, request=request)


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user