from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import ensure_utc
from app.database import get_db
from app.models.event import Event
from app.models.rule import DetectionRule
from app.models.user import User
from app.services.audit import log_action

router = APIRouter(prefix="/rules", tags=["rules"])

SEVERITIES = {"info", "low", "medium", "high"}


class RuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=512)
    event_type: str | None = Field(default=None, max_length=128)
    source: str | None = Field(default=None, max_length=128)
    category: str | None = Field(default=None, max_length=64)
    application: str | None = Field(default=None, max_length=255)
    window_hours: int = Field(default=24, ge=1, le=720)
    min_count: int = Field(default=1, ge=1, le=10000)
    severity: str = "medium"


def rule_alerts(db: Session, user_id: str) -> list[dict]:
    """Evaluate enabled detection rules against recent events; return alert dicts."""
    now = datetime.now(timezone.utc)
    alerts = []
    for rule in db.query(DetectionRule).filter(DetectionRule.user_id == user_id, DetectionRule.enabled == True).all():  # noqa: E712
        q = db.query(func.count(Event.id)).filter(Event.user_id == user_id)
        if rule.event_type:
            q = q.filter(Event.event_type == rule.event_type)
        if rule.source:
            q = q.filter(Event.source == rule.source)
        if rule.category:
            q = q.filter(Event.category == rule.category)
        if rule.application:
            q = q.filter(Event.application == rule.application)
        since = now - timedelta(hours=rule.window_hours)
        q = q.filter(Event.timestamp >= since)
        count = q.scalar() or 0
        if count >= rule.min_count:
            alerts.append({
                "severity": rule.severity, "type": "detection_rule", "title": rule.name,
                "detail": f"{count} matching events in {rule.window_hours}h (threshold {rule.min_count})",
                "resource_id": rule.id,
            })
    return alerts


@router.get("")
def list_rules(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(DetectionRule).filter(DetectionRule.user_id == user.id).order_by(DetectionRule.created_at.desc()).all()
    return [{"id": r.id, "name": r.name, "description": r.description, "event_type": r.event_type,
             "source": r.source, "category": r.category, "application": r.application,
             "window_hours": r.window_hours, "min_count": r.min_count, "severity": r.severity,
             "enabled": r.enabled,
             "created_at": ensure_utc(r.created_at).isoformat() if r.created_at else None} for r in rows]


@router.post("")
def create_rule(req: RuleCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if req.severity not in SEVERITIES:
        raise HTTPException(status_code=422, detail="severity must be info|low|medium|high")
    if not any([req.event_type, req.source, req.category, req.application]):
        raise HTTPException(status_code=422, detail="a rule needs at least one filter (event_type/source/category/application)")
    rule = DetectionRule(user_id=user.id, **req.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    log_action(db, user.id, "rule.create", resource="rule", resource_id=rule.id)
    return {"id": rule.id, "name": rule.name}


@router.patch("/{rule_id}")
def update_rule(rule_id: str, req: RuleCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rule = db.query(DetectionRule).filter(DetectionRule.id == rule_id, DetectionRule.user_id == user.id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="not found")
    if req.severity not in SEVERITIES:
        raise HTTPException(status_code=422, detail="invalid severity")
    for k, v in req.model_dump().items():
        setattr(rule, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/{rule_id}")
def delete_rule(rule_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rule = db.query(DetectionRule).filter(DetectionRule.id == rule_id, DetectionRule.user_id == user.id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="not found")
    db.delete(rule)
    db.commit()
    log_action(db, user.id, "rule.delete", resource="rule", resource_id=rule_id)
    return {"ok": True}