from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models.alert_ack import AlertAck
from app.models.event import Event
from app.models.integration import Integration
from app.models.user import User

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/retention")
def retention(user: User = Depends(get_current_user)):
    return {
        "days": settings.EVENT_RETENTION_DAYS,
        "default_days": 90,
    }


def _fingerprints_dismissed(db: Session, user_id: str) -> set[str]:
    return {a.fingerprint for a in db.query(AlertAck).filter(AlertAck.user_id == user_id, AlertAck.dismissed == True).all()}


def _get_ack(db: Session, user_id: str, fingerprint: str) -> AlertAck:
    ack = db.query(AlertAck).filter(AlertAck.user_id == user_id, AlertAck.fingerprint == fingerprint).first()
    if not ack:
        ack = AlertAck(user_id=user_id, fingerprint=fingerprint, dismissed=False)
        db.add(ack)
        db.flush()
    return ack


class DismissRequest(BaseModel):
    dismissed: bool | None = None
    acknowledged: bool | None = None
    ack: bool | None = None


@router.get("/alerts")
def alerts(
    dismissed: bool | None = Query(default=None),
    include_dismissed: bool = Query(default=False),
    show_dismissed: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(days=7)
    events = db.query(Event).filter(Event.user_id == user.id, Event.timestamp >= since).all()
    alerts_out: list[dict[str, Any]] = []
    # 1. integration failures
    for integ in db.query(Integration).filter(Integration.user_id == user.id).all():
        if integ.status == "error" or integ.last_error:
            alerts_out.append({
                "severity": "medium", "type": "integration_failure",
                "title": f"Integration '{integ.name}' has errors",
                "detail": integ.last_error or "status=error",
                "resource_id": integ.id,
                "fingerprint": f"integration_failure:{integ.id}",
            })
    # 2. unusual event frequency: source with > 3x average daily count
    counts: dict[str, int] = {}
    for e in events:
        counts.setdefault(e.source, 0)
        counts[e.source] += 1
    if counts:
        avg = sum(counts.values()) / len(counts)
        for src, c in counts.items():
            if c > max(5, avg * 3):
                alerts_out.append({
                    "severity": "low", "type": "unusual_frequency",
                    "title": f"Unusual event volume from {src}",
                    "detail": f"{c} events in 7 days (avg across sources {avg:.1f})",
                    "fingerprint": f"unusual_frequency:{src}",
                })
    # 3. unavailable permissions recorded
    unavail = [e for e in events if e.permission_status == "unavailable"]
    if unavail:
        alerts_out.append({
            "severity": "info", "type": "data_unavailable",
            "title": "Some data sources are unavailable",
            "detail": f"{len(unavail)} events marked unavailable (API/permission limits).",
            "fingerprint": "data_unavailable",
        })
    # 4. suspicious auth: repeated login failures? recorded as audit; check events
    auth_events = [e for e in events if e.event_type.startswith("auth.") or "login" in (e.event_type or "")]
    if len(auth_events) > 50:
        alerts_out.append({
            "severity": "high", "type": "suspicious_auth_volume",
            "title": "High volume of authentication events",
            "detail": f"{len(auth_events)} auth events in 7 days.",
            "fingerprint": "suspicious_auth_volume",
        })
    # 5. user-defined detection rules
    from app.api.v1.rules import rule_alerts
    alerts_out.extend(rule_alerts(db, user.id))

    dismissed_set = _fingerprints_dismissed(db, user.id)
    for a in alerts_out:
        fp = a.get("fingerprint")
        a["dismissed"] = bool(fp and fp in dismissed_set)
        if "fingerprint" not in a:
            a["fingerprint"] = None

    # Filtering
    if dismissed is True:
        filtered = [a for a in alerts_out if a.get("dismissed")]
    elif dismissed is False:
        filtered = [a for a in alerts_out if not a.get("dismissed")]
    elif include_dismissed or show_dismissed:
        filtered = alerts_out
    else:
        filtered = [a for a in alerts_out if not a.get("dismissed")]

    # Alert delivery for non-dismissed alerts (rate-limited).
    try:
        from app.services.notifications import deliver_alert
        for a in filtered:
            if a.get("dismissed"):
                continue
            try:
                deliver_alert(db, user, a)
            except Exception:
                pass
    except Exception:
        pass

    return {"alerts": filtered, "count": len(filtered)}


@router.post("/alerts/{fingerprint}/dismiss")
def dismiss_alert(
    fingerprint: str,
    req: DismissRequest | None = Body(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if req is None:
        desired = True
    elif req.dismissed is not None:
        desired = bool(req.dismissed)
    elif req.acknowledged is not None:
        desired = not bool(req.acknowledged)
    elif req.ack is not None:
        desired = not bool(req.ack)
    else:
        desired = True
    ack = _get_ack(db, user.id, fingerprint)
    ack.dismissed = desired
    ack.dismissed_at = datetime.now(timezone.utc) if desired else None
    ack.updated_at = datetime.now(timezone.utc)
    db.commit()
    from app.services.audit import log_action
    log_action(db, user.id, "alert.dismiss" if desired else "alert.ack", resource="alert", resource_id=fingerprint,
               details={"dismissed": desired})
    return {"ok": True, "fingerprint": fingerprint, "dismissed": ack.dismissed}


# Re-ack aliases
@router.post("/alerts/{fingerprint}/ack")
def ack_alert(fingerprint: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ack = _get_ack(db, user.id, fingerprint)
    ack.dismissed = False
    ack.dismissed_at = None
    ack.updated_at = datetime.now(timezone.utc)
    db.commit()
    from app.services.audit import log_action
    log_action(db, user.id, "alert.ack", resource="alert", resource_id=fingerprint, details={"dismissed": False})
    return {"ok": True, "fingerprint": fingerprint, "dismissed": False}


@router.post("/alerts/{fingerprint}/acknowledge")
def acknowledge_alert(fingerprint: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ack_alert(fingerprint, user, db)


@router.post("/alerts/{fingerprint}/undismiss")
def undismiss_alert(fingerprint: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ack_alert(fingerprint, user, db)


@router.get("/audit")
def audit_log(limit: int = 100, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models.audit import AuditLog
    rows = db.query(AuditLog).filter(AuditLog.user_id == user.id).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [{"id": r.id, "action": r.action, "resource": r.resource, "resource_id": r.resource_id,
             "details": r.details, "status": r.status, "ip_address": r.ip_address,
             "created_at": r.created_at.isoformat()} for r in rows]