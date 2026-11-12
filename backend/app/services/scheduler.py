"""Background sync + retention loop.

Uses APScheduler's ``BackgroundScheduler``. Honours ``AUTO_SYNC_ENABLED``,
``SYNC_INTERVAL_MINUTES`` and ``EVENT_RETENTION_DAYS``.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.metrics import SYNC_FAILURES_TOTAL, record_scheduler_run
from app.models.event import Event
from app.models.integration import Integration

logger = logging.getLogger("ghosttrace.scheduler")

_scheduler = None
scheduler = None


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
            result = await inst.sync()
            synced += 1
        except Exception as e:
            logger.warning("scheduled sync failed for integration %s: %s", integ.id, e)
            integ.status = "error"
            integ.last_error = str(e)[:500]
            db.commit()
            result = {"ok": False, "error": str(e)}
        # Count sync failures (exception or reported failure).
        if isinstance(result, dict) and not result.get("ok", True):
            try:
                SYNC_FAILURES_TOTAL.labels(kind=integ.kind).inc()
            except Exception:
                pass
        # Alert delivery on sync errors.
        try:
            from app.models.user import User
            from app.services.notifications import deliver_alert
            user = db.get(User, integ.user_id)
            if user and (integ.status == "error" or integ.last_error or (isinstance(result, dict) and not result.get("ok", True))):
                deliver_alert(db, user, {
                    "fingerprint": f"integration_failure:{integ.id}",
                    "severity": "medium",
                    "type": "integration_failure",
                    "title": f"Integration '{integ.name}' has errors",
                    "detail": integ.last_error or (result.get("error") if isinstance(result, dict) else None) or "status=error",
                    "resource_id": integ.id,
                })
        except Exception:
            pass
    return synced


def run_retention(db: Session) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.EVENT_RETENTION_DAYS)
    res = db.execute(delete(Event).where(Event.timestamp < cutoff))
    db.commit()
    return res.rowcount


def _tick() -> None:
    logger.info("scheduler tick starting")
    db = SessionLocal()
    try:
        synced = asyncio.run(sync_due_integrations(db))
        deleted = run_retention(db)
        if synced or deleted:
            logger.info("scheduler tick: synced=%d retention_deleted=%d", synced, deleted)
    except Exception as e:
        logger.warning("scheduler tick failed: %s", e)
    finally:
        db.close()
    record_scheduler_run()


def start_scheduler():
    global _scheduler
    if not settings.AUTO_SYNC_ENABLED:
        logger.info("auto sync disabled; scheduler not started")
        return None
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger

    interval = max(1, int(settings.SYNC_INTERVAL_MINUTES))
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(
        _tick,
        trigger=IntervalTrigger(minutes=interval),
        id="ghosttrace-sync",
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc),
        max_instances=1,
        coalesce=True,
    )
    sched.start()
    global scheduler
    _scheduler = sched
    scheduler = sched
    logger.info("scheduler started (interval=%sm, retention=%sd)", interval, settings.EVENT_RETENTION_DAYS)
    return sched


def stop_scheduler(sched=None) -> None:
    global _scheduler, scheduler
    target = sched if sched is not None else _scheduler
    if target is not None:
        try:
            target.shutdown(wait=False)
        except Exception:
            pass
    _scheduler = None
    scheduler = None
    logger.info("scheduler stopped")


async def scheduler_loop(stop=None):
    """Compatibility shim for the previous asyncio-based loop."""
    sched = start_scheduler() if settings.AUTO_SYNC_ENABLED else None
    if stop is not None and hasattr(stop, "wait"):
        try:
            await stop.wait()
        except Exception:
            pass
    else:
        # keep running until cancelled
        import asyncio as _a
        try:
            while True:
                await _a.sleep(3600)
        except (asyncio.CancelledError, Exception):
            pass
    stop_scheduler(sched)
