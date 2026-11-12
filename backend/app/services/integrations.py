from sqlalchemy.orm import Session

from app.integrations.registry import get_integration_class
from app.models.account import ConnectedAccount
from app.models.integration import Integration


def build_integration(db: Session, user_id: str, integ: Integration):
    account = None
    if integ.account_id:
        account = db.get(ConnectedAccount, integ.account_id)
    cls = get_integration_class(integ.kind)
    if not cls:
        return None
    return cls(user_id=user_id, account=account, integration=integ, db=db)


def list_integrations(db, user_id):
    return db.query(Integration).filter(Integration.user_id == user_id).all()


def get_integration(db, user_id, integ_id):
    return db.query(Integration).filter(Integration.id == integ_id, Integration.user_id == user_id).first()
