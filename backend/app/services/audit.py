from sqlalchemy.orm import Session
from app.models.audit import AuditLog


def log_action(db: Session, user_id=None, action="", resource=None, resource_id=None, details=None, ip=None, ua=None, status="success"):
    db.add(AuditLog(user_id=user_id, action=action, resource=resource, resource_id=resource_id,
                    details=details, ip_address=ip, user_agent=ua, status=status))
    db.commit()
