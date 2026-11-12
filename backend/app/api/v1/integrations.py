import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.integration import Integration
from app.models.account import ConnectedAccount
from app.schemas.account import IntegrationOut, AccountOut
from app.services.integrations import build_integration, list_integrations, get_integration
from app.integrations.registry import available_kinds

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/kinds")
def kinds(user: User = Depends(get_current_user)):
    return {"kinds": available_kinds()}


@router.get("/accounts", response_model=list[AccountOut])
def accounts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(ConnectedAccount).filter(ConnectedAccount.user_id == user.id).all()
    out = []
    for a in rows:
        o = AccountOut.model_validate(a)
        o.scopes = a.scopes
        o.metadata = a.metadata_json
        o.token_expires_at = a.token_expires_at.isoformat() if a.token_expires_at else None
        o.created_at = a.created_at.isoformat()
        out.append(o)
    return out


@router.get("", response_model=list[IntegrationOut])
def list_(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = list_integrations(db, user.id)
    out = []
    for i in rows:
        o = IntegrationOut.model_validate(i)
        o.last_sync_at = i.last_sync_at.isoformat() if i.last_sync_at else None
        o.created_at = i.created_at.isoformat()
        out.append(o)
    return out


@router.post("")
def create_integration(kind: str, name: str, config: dict | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if kind not in available_kinds():
        raise HTTPException(status_code=400, detail=f"Unknown kind {kind}")
    if kind == "github" and not (config or {}).get("username"):
        raise HTTPException(status_code=422, detail="GitHub integration requires a username")
    cfg = dict(config or {})
    # Encrypt secrets in the free-form config before storing them.
    from app.core.security import encrypt_secret
    for field in ("access_token", "password"):
        if cfg.get(field):
            cfg[field + "_enc"] = encrypt_secret(str(cfg.pop(field)))
    integ = Integration(user_id=user.id, kind=kind, name=name, config=cfg)
    db.add(integ)
    db.commit()
    db.refresh(integ)
    return {"id": integ.id, "kind": integ.kind, "name": integ.name}


@router.get("/{integ_id}")
def get_(integ_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    integ = get_integration(db, user.id, integ_id)
    if not integ:
        raise HTTPException(status_code=404, detail="not found")
    inst = build_integration(db, user.id, integ)
    caps = [c.to_dict() for c in inst.capabilities()] if inst else []
    return {"id": integ.id, "kind": integ.kind, "name": integ.name, "status": integ.status,
            "last_sync_at": integ.last_sync_at.isoformat() if integ.last_sync_at else None,
            "last_error": integ.last_error, "config": integ.config, "capabilities": caps}


@router.post("/{integ_id}/sync")
async def sync(integ_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    integ = get_integration(db, user.id, integ_id)
    if not integ:
        raise HTTPException(status_code=404, detail="not found")
    inst = build_integration(db, user.id, integ)
    if not inst:
        raise HTTPException(status_code=400, detail="unsupported kind")
    result = await inst.sync()
    return result


@router.delete("/{integ_id}")
def delete_(integ_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    integ = get_integration(db, user.id, integ_id)
    if not integ:
        raise HTTPException(status_code=404, detail="not found")
    db.delete(integ)
    db.commit()
    return {"ok": True}


@router.delete("/accounts/{account_id}")
def disconnect_account(account_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    acct = db.query(ConnectedAccount).filter(ConnectedAccount.id == account_id, ConnectedAccount.user_id == user.id).first()
    if not acct:
        raise HTTPException(status_code=404, detail="not found")
    # revoke google token if possible
    if acct.provider == "google":
        from app.core.security import decrypt_secret
        tok = decrypt_secret(acct.access_token_enc or "")
        if tok:
            try:
                import httpx
                httpx.post("https://oauth2.googleapis.com/revoke", params={"token": tok}, timeout=15)
            except Exception:
                pass
    db.delete(acct)
    db.commit()
    from app.services.audit import log_action
    log_action(db, user.id, "account.disconnect", resource="account", resource_id=account_id)
    return {"ok": True}
