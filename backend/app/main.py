from contextlib import asynccontextmanager

# Optional Sentry/GlitchTip init (no-op when SENTRY_DSN is unset).
from app.config import settings

if getattr(settings, "SENTRY_DSN", ""):
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.APP_ENV)
    except Exception:
        pass

from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

import app.integrations.activitywatch
import app.integrations.android
import app.integrations.github
import app.integrations.google
import app.integrations.ios
import app.integrations.wazuh
from app.api.deps import get_current_user
from app.api.v1 import (
    admin,
    apikeys,
    auth,
    devices,
    events,
    insights,
    integrations,
    reports,
    rules,
    security,
    takeout,
)
from app.database import Base, engine, get_db
from app.metrics import HTTP_REQUESTS_TOTAL, metrics_text
from app.models import *
from app.models.user import User

if settings.APP_ENV == "development":
    Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if settings.AUTO_SYNC_ENABLED:
        from app.services.scheduler import start_scheduler
        scheduler = start_scheduler()
        app.state.scheduler = scheduler
    yield
    if scheduler is not None:
        from app.services.scheduler import stop_scheduler
        stop_scheduler(scheduler)

app: FastAPI = FastAPI(title=settings.APP_NAME, version="0.1.0", debug=settings.DEBUG, lifespan=lifespan)  # type: ignore[no-redef]
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.auth import limiter

app.state.limiter = limiter  # type: ignore[attr-defined]
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[attr-defined]

app.add_middleware(  # type: ignore[attr-defined]
    CORSMiddleware,
    allow_origins=settings.cors_list(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Device-Key"],
)


@app.middleware("http")  # type: ignore[attr-defined]
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    if settings.APP_ENV == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.middleware("http")  # type: ignore[attr-defined]
async def metrics_http_middleware(request, call_next):
    response = await call_next(request)
    try:
        HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            path=request.url.path,
            status_code=str(response.status_code),
        ).inc()
    except Exception:
        pass
    return response


@app.get("/health")  # type: ignore[attr-defined]
def health():
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/ready")  # type: ignore[attr-defined]
def ready(db=Depends(get_db)):
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/metrics")  # type: ignore[attr-defined]
def metrics():
    from app.metrics import refresh_scheduler_age
    refresh_scheduler_age()
    return Response(content=metrics_text(), media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/api/v1/overview")  # type: ignore[attr-defined]
def overview(user: User = Depends(get_current_user), db=Depends(get_db)):
    from app.models.account import ConnectedAccount
    from app.models.device import Device
    from app.models.event import Event
    from app.models.integration import Integration
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


app.include_router(auth.router, prefix="/api/v1")  # type: ignore[attr-defined]
app.include_router(integrations.router, prefix="/api/v1")  # type: ignore[attr-defined]
app.include_router(events.router, prefix="/api/v1")  # type: ignore[attr-defined]
app.include_router(devices.router, prefix="/api/v1")  # type: ignore[attr-defined]
app.include_router(reports.router, prefix="/api/v1")  # type: ignore[attr-defined]
app.include_router(security.router, prefix="/api/v1")  # type: ignore[attr-defined]
app.include_router(admin.router, prefix="/api/v1")  # type: ignore[attr-defined]
app.include_router(apikeys.router, prefix="/api/v1")  # type: ignore[attr-defined]
app.include_router(rules.router, prefix="/api/v1")  # type: ignore[attr-defined]
app.include_router(insights.router, prefix="/api/v1")  # type: ignore[attr-defined]
app.include_router(takeout.router, prefix="/api/v1")  # type: ignore[attr-defined]
