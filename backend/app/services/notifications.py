"""Alert delivery: email (SMTP) + user webhook, rate-limited and audited."""
import logging
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models.alert_ack import AlertAck
from app.models.user import User
from app.services.audit import log_action

logger = logging.getLogger("ghosttrace.notifications")

RATE_LIMIT_HOURS = 24


def _smtp_configured() -> bool:
    return bool(settings.SMTP_HOST) or bool(settings.EMAIL_VERIFY_ENABLED)


def send_alert_email(to_email: str, subject: str, body: str) -> bool:
    """Send an alert email via the configured SMTP vars. Best-effort."""
    if not _smtp_configured():
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_USER or "noreply@ghosttrace.local"
        msg["To"] = to_email
        msg.set_content(body)
        with smtplib.SMTP(settings.SMTP_HOST or "localhost", settings.SMTP_PORT) as server:
            if settings.SMTP_USER:
                try:
                    server.starttls()
                except Exception:
                    pass
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("Failed to send alert email to %s: %s", to_email, exc)
        return False


def send_alert_webhook(webhook_url: str, payload: dict) -> bool:
    """POST an alert payload to the user's webhook URL."""
    if not webhook_url:
        return False
    try:
        r = httpx.post(webhook_url, json=payload, timeout=15)
        return 200 <= r.status_code < 300
    except Exception as exc:
        logger.warning("Failed to post alert webhook to %s: %s", webhook_url, exc)
        return False


def _get_ack(db: Session, user_id: str, fingerprint: str) -> AlertAck:
    ack = db.query(AlertAck).filter(AlertAck.user_id == user_id, AlertAck.fingerprint == fingerprint).first()
    if not ack:
        ack = AlertAck(user_id=user_id, fingerprint=fingerprint, dismissed=False)
        db.add(ack)
        db.flush()
    return ack


def _rate_limited(ack: AlertAck) -> bool:
    if not ack.last_notified_at:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(hours=RATE_LIMIT_HOURS)
    la = ack.last_notified_at
    if la.tzinfo is None:
        la = la.replace(tzinfo=timezone.utc)
    return la >= cutoff


def deliver_alert(db: Session, user: User, alert: dict, *, force: bool = False) -> bool:
    """Deliver a single alert via email/webhook, rate-limited to once per 24h per
    fingerprint. Records an audit log entry when delivery is attempted."""
    fingerprint = alert.get("fingerprint")
    if not fingerprint:
        return False
    ack = _get_ack(db, user.id, fingerprint)
    if (not force) and _rate_limited(ack):
        db.commit()
        return False

    payload = {
        "fingerprint": fingerprint,
        "severity": alert.get("severity"),
        "type": alert.get("type"),
        "title": alert.get("title"),
        "detail": alert.get("detail"),
        "resource_id": alert.get("resource_id"),
    }

    delivered = False
    if _smtp_configured():
        try:
            send_alert_email(user.email, f"[Ghosttrace] {alert.get('title')}", str(alert.get("detail") or alert.get("title") or ""))
            delivered = True
        except Exception:
            pass
    if getattr(user, "webhook_url", None):
        try:
            send_alert_webhook(user.webhook_url, payload)
            delivered = True
        except Exception:
            pass

    ack.last_notified_at = datetime.now(timezone.utc)
    db.commit()
    try:
        log_action(db, user.id, "alert.delivered", resource="alert", resource_id=fingerprint,
                   details={"type": alert.get("type"), "title": alert.get("title")})
    except Exception:
        pass
    return delivered


# Backwards/alternate names
notify_alert = deliver_alert
send_alert = deliver_alert
dispatch_alert = deliver_alert