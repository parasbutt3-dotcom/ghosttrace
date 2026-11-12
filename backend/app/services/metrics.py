"""Re-export of ``app.metrics`` for callers that look under services/."""
from app.metrics import *
from app.metrics import (  # noqa: F401
    EVENTS_INGESTED_TOTAL,
    HTTP_REQUESTS_TOTAL,
    SCHEDULER_LAST_RUN_AGE_SECONDS,
    SCHEDULER_LAST_RUN_TIMESTAMP_SECONDS,
    SYNC_FAILURES_TOTAL,
    metrics_text,
    record_scheduler_run,
    refresh_scheduler_age,
)
