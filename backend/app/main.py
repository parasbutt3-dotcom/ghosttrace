import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine, get_db
from app.api.deps import get_current_user
from app.models import *  # noqa
import app.integrations.google  # noqa
import app.integrations.activitywatch  # noqa
import app.integrations.wazuh  # noqa
import app.integrations.android  # noqa
import app.integrations.ios  # noqa
import app.integrations.github  # noqa
from app.models.user import User
from app.api.v1 import auth, integrations, events, devices, reports, security, admin, apikeys, rules, insights, takeout

if settings.APP_ENV == "development":
    Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = asyncio.Event()
    task = None
    if settings.AUTO_SYNC_ENABLED:
        from app.services.scheduler import scheduler_loop
        task = asyncio.create_task(scheduler_loop(stop))
    yield
    if task:
        stop.set()
        task.cancel()


app = FastAPI(title=settings.APP_NAME, version="0.1.0", debug=settings.DEBUG, lifespan=lifespan)
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.api.v1.auth import limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Device-Key"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    if settings.APP_ENV == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/ready")
def ready(db=Depends(get_db)):
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/v1/overview")
def overview(user: User = Depends(get_current_user), db=Depends(get_db)):
    from app.models.event import Event
    from app.models.integration import Integration
    from app.models.device import Device
    from app.models.account import ConnectedAccount
    uid = user.id
    return {
        "accounts": db.query(ConnectedAccount).filter(ConnectedAccount.user_id == uid).count(),
        "integrations": db.query(Integration).filter(Integration.user_id == uid).count(),
        "devices": db.query(Device).filter(Device.user_id == uid).count(),
        "events": db.query(Event).filter(Event.user_id == uid).count(),
        "active_integrations": db.query(Integration).filter(Integration.user_id == uid, Integration.enabled == True).count(),
        "recent_events": [
            {"id": e.id, "timestamp": e.timestamp.isoformat(), "source": e.source, "application": e.application,
             "event_type": e.event_type, "description": e.description}
            for e in db.query(Event).filter(Event.user_id == uid).order_by(Event.timestamp.desc()).limit(10).all()
        ],
    }


app.include_router(auth.router, prefix="/api/v1")
app.include_router(integrations.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")
app.include_router(devices.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(security.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(apikeys.router, prefix="/api/v1")
app.include_router(rules.router, prefix="/api/v1")
app.include_router(insights.router, prefix="/api/v1")
app.include_router(takeout.router, prefix="/api/v1")
