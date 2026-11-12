import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.device import Device
from app.models.integration import Integration
from app.schemas.account import DeviceOut
from app.schemas.device import TelemetryIn
from app.services.events import ingest_event
from app.api.v1.auth import limiter

router = APIRouter(prefix="/devices", tags=["devices"])


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


@router.get("")
def list_devices(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Device).filter(Device.user_id == user.id).all()
    out = []
    for d in rows:
        o = DeviceOut.model_validate(d)
        o.last_seen_at = d.last_seen_at.isoformat() if d.last_seen_at else None
        o.created_at = d.created_at.isoformat()
        out.append(o)
    return out


@router.post("/register")
def register_device(name: str, device_type: str = "android", platform: str | None = None,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # ensure an android integration exists
    integ = db.query(Integration).filter(Integration.user_id == user.id, Integration.kind == "android").first()
    if not integ:
        integ = Integration(user_id=user.id, kind="android", name="Android Companion")
        db.add(integ)
        db.commit()
        db.refresh(integ)
    raw_key = secrets.token_urlsafe(32)
    dev = Device(user_id=user.id, integration_id=integ.id, name=name, device_type=device_type,
                 platform=platform, device_key_hash=_hash_key(raw_key), status="active")
    db.add(dev)
    db.commit()
    db.refresh(dev)
    return {"id": dev.id, "name": dev.name, "device_key": raw_key,
            "note": "Store this key on the device; it will not be shown again."}


@router.post("/telemetry")
@limiter.limit("60/minute")
def telemetry(payload: TelemetryIn, x_device_key: str = Header(..., alias="X-Device-Key"), request: Request = None, db: Session = Depends(get_db)):
    dev = db.query(Device).filter(Device.device_key_hash == _hash_key(x_device_key)).first()
    if not dev:
        raise HTTPException(status_code=401, detail="invalid device key")
    user_id = dev.user_id
    dev.last_seen_at = datetime.now(timezone.utc)
    if payload.battery_level is not None:
        dev.battery_level = payload.battery_level
    if payload.network_type is not None:
        dev.network_type = payload.network_type
    if payload.location is not None:
        dev.last_location = payload.location
    if payload.app_version is not None:
        dev.app_version = payload.app_version
    if payload.os_version is not None:
        dev.os_version = payload.os_version
    db.commit()

    created = 0
    for e in payload.events:
        ingest_event(
            db, user_id, device_id=dev.id, source="android_companion",
            application=e.application, event_type=e.event_type,
            timestamp=e.timestamp, category=e.category,
            description=e.description, metadata=e.metadata,
            collection_method=e.collection_method, permission_status=e.permission_status,
            confidence=e.confidence, dedup_key=e.dedup_key,
        )
        created += 1
    # device status event
    ingest_event(db, user_id, device_id=dev.id, source="android_companion", application="Device",
                event_type="device.status", category="device",
                description=f"Device {dev.name} reported telemetry",
                metadata={"battery": dev.battery_level, "network": dev.network_type, "location": dev.last_location},
                collection_method="device_sdk", permission_status="authorized", confidence=1.0,
                dedup_key=f"android:status:{dev.id}:{int(datetime.now(timezone.utc).timestamp()//60)}")
    return {"ok": True, "events_created": created + 1}


@router.delete("/{device_id}")
def delete_device(device_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    dev = db.query(Device).filter(Device.id == device_id, Device.user_id == user.id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="not found")
    db.delete(dev)
    db.commit()
    return {"ok": True}
