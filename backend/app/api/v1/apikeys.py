from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import ensure_utc, generate_api_key
from app.database import get_db
from app.models.apikey import ApiKey
from app.models.user import User
from app.services.audit import log_action

router = APIRouter(prefix="/apikeys", tags=["apikeys"])


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


@router.post("")
def create_key(req: ApiKeyCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    full, digest, prefix = generate_api_key()
    ak = ApiKey(user_id=user.id, name=req.name, key_hash=digest, prefix=prefix)
    db.add(ak)
    db.commit()
    db.refresh(ak)
    log_action(db, user.id, "apikey.create", resource="apikey", resource_id=ak.id)
    return {"id": ak.id, "name": ak.name, "prefix": prefix, "key": full,
            "note": "Copy this key now — it is stored hashed and shown only once. Use it as: Authorization: Bearer <key>"}


@router.get("")
def list_keys(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(ApiKey).filter(ApiKey.user_id == user.id).order_by(ApiKey.created_at.desc()).all()
    return [{"id": a.id, "name": a.name, "prefix": a.prefix,
             "created_at": ensure_utc(a.created_at).isoformat() if a.created_at else None,
             "last_used_at": ensure_utc(a.last_used_at).isoformat() if a.last_used_at else None} for a in rows]


@router.delete("/{key_id}")
def revoke_key(key_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ak = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.user_id == user.id).first()
    if not ak:
        raise HTTPException(status_code=404, detail="not found")
    db.delete(ak)
    db.commit()
    log_action(db, user.id, "apikey.revoke", resource="apikey", resource_id=key_id)
    return {"ok": True}