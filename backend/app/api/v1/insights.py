from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.device import Device
from app.models.event import Event
from app.models.integration import Integration
from app.models.user import User

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("")
def insights(days: int = 14, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    days = max(1, min(days, 90))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = lambda: db.query(Event).filter(Event.user_id == user.id, Event.timestamp >= since)

    # activity by hour of day (UTC)
    hourly = dict.fromkeys(range(24), 0)
    for ts, in q().with_entities(Event.timestamp).all():
        hourly[ts.hour] = hourly.get(ts.hour, 0) + 1

    # activity by weekday (Mon=0)
    weekdays = dict.fromkeys(range(7), 0)
    for ts, in q().with_entities(Event.timestamp).all():
        weekdays[ts.weekday()] += 1

    top_apps = (q().with_entities(Event.application, func.count(Event.id))
                .filter(Event.application.isnot(None))
                .group_by(Event.application).order_by(func.count(Event.id).desc()).limit(10).all())

    by_category = (q().with_entities(Event.category, func.count(Event.id))
                   .group_by(Event.category).all())

    by_source = (q().with_entities(Event.source, func.count(Event.id))
                 .group_by(Event.source).all())

    # active days + streak
    day_expr = func.date(Event.timestamp)
    active_days = (q().with_entities(day_expr).distinct().count())
    streak = 0
    cursor = datetime.now(timezone.utc).date()
    days_set = {str(r[0]) for r in q().with_entities(day_expr).distinct().all()}
    while str(cursor) in days_set:
        streak += 1
        cursor -= timedelta(days=1)

    # correlation counts for the big connected-account payoffs
    meetings = q().filter(Event.event_type == "calendar.event").count()
    file_edits = q().filter(Event.event_type == "drive.file_modified").count()
    git_pushes = q().filter(Event.event_type == "git.push").count()
    login_alerts = q().filter(Event.event_type.like("security.%")).count()
    location_points = q().filter(Event.event_type == "location.point").count()
    place_visits = q().filter(Event.event_type == "location.place_visit").count()

    integrations = db.query(Integration).filter(Integration.user_id == user.id).all()
    devices = db.query(Device).filter(Device.user_id == user.id).all()

    return {
        "days": days,
        "total_events": q().count(),
        "hourly": [{"hour": h, "count": c} for h, c in hourly.items()],
        "weekdays": [{"weekday": d, "count": c} for d, c in weekdays.items()],
        "top_applications": [{"application": a, "count": c} for a, c in top_apps],
        "by_category": [{"category": cat, "count": c} for cat, c in by_category],
        "by_source": [{"source": s, "count": c} for s, c in by_source],
        "active_days": active_days,
        "current_streak": streak,
        "correlations": {"meetings": meetings, "file_edits": file_edits,
                         "git_pushes": git_pushes, "security_alerts": login_alerts,
                         "location_points": location_points, "place_visits": place_visits},
        "coverage": {
            "integrations_enabled": sum(1 for i in integrations if i.enabled),
            "integrations_error": sum(1 for i in integrations if i.status == "error"),
            "devices_seen_24h": sum(1 for d in devices if d.last_seen_at),
            "mfa_enabled": user.mfa_enabled,
        },
    }