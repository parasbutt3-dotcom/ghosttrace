from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.config import settings
from app.database import get_db
from app.models.event import Event
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/retention/run")
def run_retention(user: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    from app.services.audit import log_action

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.EVENT_RETENTION_DAYS)
    res = db.execute(delete(Event).where(Event.user_id == user.id, Event.timestamp < cutoff))
    db.commit()
    deleted = int(getattr(res, "rowcount", 0) or 0)
    log_action(db, user.id, "retention.run", details={"deleted": deleted, "cutoff": cutoff.isoformat()})
    return {"deleted": deleted, "cutoff": cutoff.isoformat()}