"""Prometheus metrics for GHOSTTRACE.

All metrics use the default registry so ``prometheus_client.generate_latest``
renders them for the ``/metrics`` endpoint.
"""
import time

from prometheus_client import Counter, Gauge

# HTTP traffic
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests handled.",
    ["method", "path", "status_code"],
)
REQUESTS_TOTAL = HTTP_REQUESTS_TOTAL
REQUEST_COUNT = HTTP_REQUESTS_TOTAL

# Events ingested, labelled by source
EVENTS_INGESTED_TOTAL = Counter(
    "events_ingested_total",
    "Total events ingested, by source.",
    ["source"],
)
EVENTS_INGESTED = EVENTS_INGESTED_TOTAL

# Integration sync failures
SYNC_FAILURES_TOTAL = Counter(
    "sync_failures_total",
    "Total integration sync failures.",
    ["kind"],
)
SYNC_FAILURES = SYNC_FAILURES_TOTAL

# Scheduler observability
SCHEDULER_LAST_RUN_TIMESTAMP_SECONDS = Gauge(
    "scheduler_last_run_timestamp_seconds",
    "Unix timestamp of the last scheduler run.",
)
SCHEDULER_LAST_RUN_AGE_SECONDS = Gauge(
    "scheduler_last_run_age_seconds",
    "Seconds since the last scheduler run.",
)

_last_scheduler_run: dict = {"ts": None}


def record_scheduler_run() -> None:
    now = time.time()
    _last_scheduler_run["ts"] = now
    SCHEDULER_LAST_RUN_TIMESTAMP_SECONDS.set(now)
    SCHEDULER_LAST_RUN_AGE_SECONDS.set(0)


def refresh_scheduler_age() -> None:
    ts = _last_scheduler_run["ts"]
    if ts is not None:
        SCHEDULER_LAST_RUN_AGE_SECONDS.set(time.time() - ts)


def metrics_text() -> bytes:
    refresh_scheduler_age()
    from prometheus_client import generate_latest

    return generate_latest()
