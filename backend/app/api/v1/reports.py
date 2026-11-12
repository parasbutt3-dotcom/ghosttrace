import csv
import io
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.event import Event
from app.models.user import User

router = APIRouter(prefix="/reports", tags=["reports"])


def _csv_safe(value) -> str:
    # Guard spreadsheet formula injection: prefix cells starting with = + - @ TAB CR
    if value is None:
        return ""
    s = str(value)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


@router.get("/summary")
def summary(days: int = 7, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = db.query(Event).filter(Event.user_id == user.id, Event.timestamp >= since)
    total = q.count()
    by_source = q.with_entities(Event.source, func.count(Event.id)).group_by(Event.source).all()
    by_category = q.with_entities(Event.category, func.count(Event.id)).group_by(Event.category).all()
    by_app = q.with_entities(Event.application, func.count(Event.id)).group_by(Event.application).order_by(func.count(Event.id).desc()).limit(10).all()
    return {
        "days": days,
        "total": total,
        "by_source": [{"source": s, "count": c} for s, c in by_source],
        "by_category": [{"category": c, "count": n} for c, n in by_category],
        "top_applications": [{"application": a, "count": c} for a, c in by_app],
    }


@router.get("/export")
def export(format: str = Query("json", pattern="^(json|csv)$"), days: int = 30,
          user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.query(Event).filter(Event.user_id == user.id, Event.timestamp >= since).order_by(Event.timestamp.desc()).all()
    if format == "json":
        data = [{
            "id": e.id, "timestamp": e.timestamp.isoformat(), "source": e.source,
            "application": e.application, "event_type": e.event_type, "category": e.category,
            "description": e.description, "collection_method": e.collection_method,
            "permission_status": e.permission_status, "confidence": e.confidence,
            "metadata": e.metadata_json,
        } for e in rows]
        buf = io.StringIO()
        json.dump(data, buf, indent=2, default=str)
        buf.seek(0)
        return StreamingResponse(iter([buf.getvalue()]), media_type="application/json",
                                 headers={"Content-Disposition": "attachment; filename=ghosttrace_export.json"})

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "timestamp", "source", "application", "event_type", "category", "description", "collection_method", "permission_status", "confidence"])
    for e in rows:
        w.writerow([e.id, e.timestamp.isoformat(), _csv_safe(e.source), _csv_safe(e.application), _csv_safe(e.event_type),
                    _csv_safe(e.category), _csv_safe(e.description), _csv_safe(e.collection_method),
                    _csv_safe(e.permission_status), e.confidence])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=ghosttrace_export.csv"})
