"""Background sync + retention loop.

Runs every SYNC_INTERVAL_MINUTES:
- syncs enabled integrations whose last sync is older than the interval
- deletes events past EVENT_RETENTION_DAYS

Designed for single-process dev; production would use Celery/APScheduler,
but keeping zero extra deps means the loop is testable and starts with the app.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.event import Event
from app.models.integration import Integration

logger = logging.getLogger("ghosttrace.scheduler")


async def sync_due_integrations(db: Session) -> int:
    from app.services.integrations import build_integration
    from app.core.security import ensure_utc
    interval = timedelta(minutes=settings.SYNC_INTERVAL_MINUTES)
    now = datetime.now(timezone.utc)
    due = [
        i for i in db.query(Integration).filter(Integration.enabled == True).all()  # noqa: E712
        if ensure_utc(i.last_sync_at) is None or ensure_utc(i.last_sync_at) < now - interval
    ]
    synced = 0
    for integ in due:
        inst = build_integration(db, integ.user_id, integ)
        if not inst:
            continue
        try:
            await inst.sync()
            synced += 1
        except Exception as e:
            logger.warning("scheduled sync failed for integration %s: %s", integ.id, e)
            integ.status = "error"
            integ.last_error = str(e)[:500]
            db.commit()
    return synced


def run_retention(db: Session) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.EVENT_RETENTION_DAYS)
    res = db.execute(delete(Event).where(Event.timestamp < cutoff))
    db.commit()
    return res.rowcount


async def scheduler_loop(stop: asyncio.Event):
    logger.info("scheduler started (interval=%sm, retention=%sd)",
                settings.SYNC_INTERVAL_MINUTES, settings.EVENT_RETENTION_DAYS)
    while not stop.is_set():
        db = SessionLocal()
        try:
            synced = await sync_due_integrations(db)
            deleted = run_retention(db)
            if synced or deleted:
                logger.info("scheduler tick: synced=%d retention_deleted=%d", synced, deleted)
        except Exception as e:
            logger.warning("scheduler tick failed: %s", e)
        finally:
            db.close()
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.SYNC_INTERVAL_MINUTES * 60)
        except asyncio.TimeoutError:
            pass
    logger.info("scheduler stopped")