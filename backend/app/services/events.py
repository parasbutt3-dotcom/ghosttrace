from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.event import Event

try:
    from app.metrics import EVENTS_INGESTED_TOTAL
except Exception:  # pragma: no cover
    EVENTS_INGESTED_TOTAL = None


def _parse_ts(ts):
    if ts is None:
        return datetime.now(timezone.utc)
    if isinstance(ts, datetime):
        return ts
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)


def ingest_event(db: Session, user_id: str, *, source: str, event_type: str,
                 timestamp=None, account_id=None, device_id=None, integration_kind=None,
                 application=None, category=None, description=None, metadata=None,
                 collection_method="api", permission_status="authorized", confidence=1.0,
                 dedup_key=None, raw=None) -> Event | None:
    # dedup
    if dedup_key:
        existing = db.query(Event).filter(Event.user_id == user_id, Event.dedup_key == dedup_key).first()
        if existing:
            # update mutable fields lightly
            existing.timestamp = _parse_ts(timestamp) if timestamp else existing.timestamp
            if description:
                existing.description = description
            if metadata:
                existing.metadata_json = metadata
            db.commit()
            return existing
    ev = Event(
        user_id=user_id,
        account_id=account_id,
        device_id=device_id,
        integration_kind=integration_kind,
        source=source,
        timestamp=_parse_ts(timestamp),
        application=application,
        event_type=event_type,
        category=category,
        description=description,
        metadata_json=metadata,
        collection_method=collection_method,
        permission_status=permission_status,
        confidence=confidence,
        dedup_key=dedup_key,
        raw=raw,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    if EVENTS_INGESTED_TOTAL is not None:
        try:
            EVENTS_INGESTED_TOTAL.labels(source=source).inc()
        except Exception:
            pass
    return ev


def query_events(db: Session, user_id: str, filters: dict, limit: int = 100, offset: int = 0):
    q = db.query(Event).filter(Event.user_id == user_id)
    if filters.get("source"):
        q = q.filter(Event.source == filters["source"])
    if filters.get("application"):
        q = q.filter(Event.application == filters["application"])
    if filters.get("event_type"):
        q = q.filter(Event.event_type == filters["event_type"])
    if filters.get("category"):
        q = q.filter(Event.category == filters["category"])
    if filters.get("device_id"):
        q = q.filter(Event.device_id == filters["device_id"])
    if filters.get("account_id"):
        q = q.filter(Event.account_id == filters["account_id"])
    if filters.get("start"):
        q = q.filter(Event.timestamp >= _parse_ts(filters["start"]))
    if filters.get("end"):
        q = q.filter(Event.timestamp <= _parse_ts(filters["end"]))
    if filters.get("q"):
        like = f"%{filters['q']}%"
        q = q.filter((Event.description.ilike(like)) | (Event.application.ilike(like)) | (Event.event_type.ilike(like)))
    q = q.order_by(Event.timestamp.desc())
    total = q.count()
    items = q.offset(offset).limit(limit).all()
    return items, total
