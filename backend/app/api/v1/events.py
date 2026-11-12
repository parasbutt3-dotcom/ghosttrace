from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_current_user_or_api_key
from app.api.v1.auth import limiter
from app.database import get_db
from app.models.user import User
from app.schemas.event import EventIn, EventOut
from app.services.events import ingest_event, query_events

router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
def list_events(
    source: str | None = None,
    application: str | None = None,
    event_type: str | None = None,
    category: str | None = None,
    device_id: str | None = None,
    account_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    q: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    user: User = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    filters = {"source": source, "application": application, "event_type": event_type, "category": category,
                   "device_id": device_id, "account_id": account_id, "start": start, "end": end, "q": q}
    items, total = query_events(db, user.id, filters, limit=limit, offset=offset)
    out = []
    for e in items:
        o = EventOut.model_validate(e)
        o.timestamp = e.timestamp.isoformat()
        o.metadata = e.metadata_json
        out.append(o)
    fetched = offset + len(items)
    return {"total": total, "items": [o.model_dump() for o in out],
            "offset": offset, "limit": limit,
            "next_offset": fetched if fetched < total else None}


@router.post("")
@limiter.limit("120/minute")
def create_event(request: Request, payload: EventIn, user: User = Depends(get_current_user_or_api_key), db: Session = Depends(get_db)):
    ts = payload.timestamp
    ev = ingest_event(
        db, user.id, source=payload.source, event_type=payload.event_type, timestamp=ts,
        account_id=payload.account_id, device_id=payload.device_id, integration_kind=payload.integration_kind,
        application=payload.application, category=payload.category, description=payload.description,
        metadata=payload.metadata, collection_method=payload.collection_method,
        permission_status=payload.permission_status, confidence=payload.confidence,
        dedup_key=payload.dedup_key, raw=payload.raw,
    )
    return {"id": ev.id if ev is not None else None}


@router.get("/stats")
def stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from sqlalchemy import func

    from app.models.event import Event
    total = db.query(func.count(Event.id)).filter(Event.user_id == user.id).scalar()
    by_source = db.query(Event.source, func.count(Event.id)).filter(Event.user_id == user.id).group_by(Event.source).all()
    by_category = db.query(Event.category, func.count(Event.id)).filter(Event.user_id == user.id).group_by(Event.category).all()
    return {
        "total": total,
        "by_source": [{"source": s, "count": c} for s, c in by_source],
        "by_category": [{"category": c, "count": n} for c, n in by_category],
    }
