from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.event import Event
from app.models.integration import Integration

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/retention")
def retention(user: User = Depends(get_current_user)):
    return {
        "days": settings.EVENT_RETENTION_DAYS,
        "default_days": 90,
    }


@router.get("/alerts")
def alerts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=7)
    events = db.query(Event).filter(Event.user_id == user.id, Event.timestamp >= since).all()
    alerts_out = []
    # 1. integration failures
    for integ in db.query(Integration).filter(Integration.user_id == user.id).all():
        if integ.status == "error" or integ.last_error:
            alerts_out.append({
                "severity": "medium", "type": "integration_failure",
                "title": f"Integration '{integ.name}' has errors",
                "detail": integ.last_error or "status=error",
                "resource_id": integ.id,
            })
    # 2. unusual event frequency: source with > 3x average daily count
    counts = {}
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
                })
    # 3. unavailable permissions recorded
    unavail = [e for e in events if e.permission_status == "unavailable"]
    if unavail:
        alerts_out.append({
            "severity": "info", "type": "data_unavailable",
            "title": "Some data sources are unavailable",
            "detail": f"{len(unavail)} events marked unavailable (API/permission limits).",
        })
    # 4. suspicious auth: repeated login failures? recorded as audit; check events
    auth_events = [e for e in events if e.event_type.startswith("auth.") or "login" in (e.event_type or "")]
    if len(auth_events) > 50:
        alerts_out.append({
            "severity": "high", "type": "suspicious_auth_volume",
            "title": "High volume of authentication events",
            "detail": f"{len(auth_events)} auth events in 7 days.",
        })
    # 5. user-defined detection rules
    from app.api.v1.rules import rule_alerts
    alerts_out.extend(rule_alerts(db, user.id))
    return {"alerts": alerts_out, "count": len(alerts_out)}


@router.get("/audit")
def audit_log(limit: int = 100, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models.audit import AuditLog
    rows = db.query(AuditLog).filter(AuditLog.user_id == user.id).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [{"id": r.id, "action": r.action, "resource": r.resource, "resource_id": r.resource_id,
             "details": r.details, "status": r.status, "ip_address": r.ip_address,
             "created_at": r.created_at.isoformat()} for r in rows]
