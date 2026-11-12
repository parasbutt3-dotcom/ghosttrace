import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_ghosttrace.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32chars-minimum-aaaa")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "QFJ-zhAIHeDkTDc8kPgFgjHhMbDO6u6_gc5XSfw69oI=")
os.environ.setdefault("AUTO_SYNC_ENABLED", "false")

import uuid
from unittest import mock

import httpx
from fastapi.testclient import TestClient
from app.main import app
from app.api.v1.auth import limiter

limiter.enabled = False
client = TestClient(app)


def _new_user(email=None):
    email = email or f"u_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "pw123456"})
    assert r.status_code == 200, r.text
    return email, {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_activitywatch_sync_success():
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import patch
    from app.integrations.activitywatch import ActivityWatchIntegration

    buckets = {"aw-watcher-window_host": {"id": "aw-watcher-window_host"},
               "aw-watcher-afk_host": {"id": "aw-watcher-afk_host"}}
    window_events = [{"id": 1, "timestamp": "2026-11-10T12:00:00Z", "duration": 60,
                      "data": {"app": "Code", "title": "main.py"}}]
    afk_events = [{"id": 2, "timestamp": "2026-11-10T12:01:00Z", "duration": 10,
                   "data": {"status": "afk"}}]

    integ = SimpleNamespace(config={"base_url": "http://aw:5600"}, id="iaw",
                            last_error=None, status="ok", last_sync_at=None)
    aw = ActivityWatchIntegration(user_id="u9", account=None, integration=integ, db=None)

    class FakeClient:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def get(self, url, **kw):
            if url.endswith("/buckets"):
                return httpx.Response(200, json=buckets, request=httpx.Request("GET", url))
            if "aw-watcher-window" in url:
                return httpx.Response(200, json=window_events, request=httpx.Request("GET", url))
            if "aw-watcher-afk" in url:
                return httpx.Response(200, json=afk_events, request=httpx.Request("GET", url))
            return httpx.Response(404, json={}, request=httpx.Request("GET", url))

    ingested = []
    with patch("httpx.AsyncClient", FakeClient), patch("app.services.events.ingest_event",
                                                        side_effect=lambda db, uid, **kw: ingested.append(kw) or SimpleNamespace(id="e")):
        summary = asyncio.run(aw.sync())

    assert summary["ok"] is True
    assert summary["events_created"] == 2
    assert set(summary["buckets"]) == set(buckets.keys())
    dks = [e["dedup_key"] for e in ingested]
    assert "aw:aw-watcher-window_host:1" in dks
    assert "aw:aw-watcher-afk_host:2" in dks


def test_activitywatch_sync_auth_failure():
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import patch
    from app.integrations.activitywatch import ActivityWatchIntegration

    integ = SimpleNamespace(config={"base_url": "http://aw:5600"}, id="iaw",
                            last_error=None, status="ok", last_sync_at=None)
    aw = ActivityWatchIntegration(user_id="u9", account=None, integration=integ, db=None)

    class FakeClient:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def get(self, url, **kw):
            return httpx.Response(401, json={"error": "unauthorized"}, request=httpx.Request("GET", url))

    with patch("httpx.AsyncClient", FakeClient):
        summary = asyncio.run(aw.sync())
    assert summary["ok"] is False
    assert "error" in summary
    assert integ.status == "error"


def test_activitywatch_sync_malformed_payload():
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import patch
    from app.integrations.activitywatch import ActivityWatchIntegration

    integ = SimpleNamespace(config={"base_url": "http://aw:5600"}, id="iaw",
                            last_error=None, status="ok", last_sync_at=None)
    aw = ActivityWatchIntegration(user_id="u9", account=None, integration=integ, db=None)

    class FakeClient:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def get(self, url, **kw):
            return httpx.Response(200, json=["not", "a", "dict"], request=httpx.Request("GET", url))

    with patch("httpx.AsyncClient", FakeClient):
        summary = asyncio.run(aw.sync())
    assert summary["ok"] is False
    assert "error" in summary


def test_wazuh_sync_success():
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import patch
    from app.integrations.wazuh import WazuhIntegration

    cfg = {"base_url": "https://wazuh:55000", "username": "wazuh", "password": "secret"}
    integ = SimpleNamespace(config=cfg, id="iwz", last_error=None, status="ok",
                            last_sync_at=None, last_sync_summary=None)
    w = WazuhIntegration(user_id="u9", account=None, integration=integ, db=None)

    agents_payload = {"data": {"affected_items": [
        {"id": "001", "name": "agent1", "status": "active"}]}}
    alerts_payload = {"data": {"affected_items": [
        {"id": "alert1", "timestamp": "2026-11-10T12:00:00Z",
         "rule": {"level": 5, "description": "SSH brute force"}}]}}

    class FakeClient:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def post(self, url, **kw):
            if "authenticate" in url:
                return httpx.Response(200, json={"data": {"token": "jwt-token"}},
                                      request=httpx.Request("POST", url))
            return httpx.Response(404, request=httpx.Request("POST", url))
        async def get(self, url, **kw):
            if "/agents" in url:
                return httpx.Response(200, json=agents_payload, request=httpx.Request("GET", url))
            if "/alerts" in url:
                return httpx.Response(200, json=alerts_payload, request=httpx.Request("GET", url))
            return httpx.Response(404, json={}, request=httpx.Request("GET", url))

    ingested = []
    with patch("httpx.AsyncClient", FakeClient), patch("app.services.events.ingest_event",
                                                        side_effect=lambda db, uid, **kw: ingested.append(kw) or SimpleNamespace(id="e")):
        summary = asyncio.run(w.sync())

    assert summary["ok"] is True
    assert summary["events_created"] == 2
    dks = [e["dedup_key"] for e in ingested]
    assert "wazuh:agent:001" in dks
    assert "wazuh:alert:alert1" in dks


def test_wazuh_sync_auth_failure():
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import patch
    from app.integrations.wazuh import WazuhIntegration

    cfg = {"base_url": "https://wazuh:55000", "username": "wazuh", "password": "secret"}
    integ = SimpleNamespace(config=cfg, id="iwz", last_error=None, status="ok",
                            last_sync_at=None, last_sync_summary=None)
    w = WazuhIntegration(user_id="u9", account=None, integration=integ, db=None)

    class FakeClient:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def post(self, url, **kw):
            return httpx.Response(401, json={"error": "unauthorized"}, request=httpx.Request("POST", url))
        async def get(self, url, **kw):
            return httpx.Response(404, json={}, request=httpx.Request("GET", url))

    with patch("httpx.AsyncClient", FakeClient):
        summary = asyncio.run(w.sync())
    assert summary["ok"] is False
    assert summary.get("error") == "authentication failed"
    assert integ.status == "error"


def test_wazuh_sync_malformed_payload():
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import patch
    from app.integrations.wazuh import WazuhIntegration

    cfg = {"base_url": "https://wazuh:55000", "username": "wazuh", "password": "secret"}
    integ = SimpleNamespace(config=cfg, id="iwz", last_error=None, status="ok",
                            last_sync_at=None, last_sync_summary=None)
    w = WazuhIntegration(user_id="u9", account=None, integration=integ, db=None)

    class FakeClient:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def post(self, url, **kw):
            if "authenticate" in url:
                return httpx.Response(200, json={"data": {"token": "jwt-token"}},
                                      request=httpx.Request("POST", url))
            return httpx.Response(404, request=httpx.Request("POST", url))
        async def get(self, url, **kw):
            if "/agents" in url:
                return httpx.Response(200, json=["bad"], request=httpx.Request("GET", url))
            if "/alerts" in url:
                return httpx.Response(200, json={"data": {"affected_items": []}},
                                      request=httpx.Request("GET", url))
            return httpx.Response(404, json={}, request=httpx.Request("GET", url))

    ingested = []
    with patch("httpx.AsyncClient", FakeClient), patch("app.services.events.ingest_event",
                                                        side_effect=lambda db, uid, **kw: ingested.append(kw) or SimpleNamespace(id="e")):
        summary = asyncio.run(w.sync())
    assert "errors" in summary
    assert summary["events_created"] == 0


def test_insights_endpoint():
    _, h = _new_user()
    client.post("/api/v1/events", json={"source": "test", "event_type": "foo.bar",
                                        "description": "hi", "application": "App"}, headers=h)
    r = client.get("/api/v1/insights", headers=h)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["total_events"] >= 1
    assert len(d["hourly"]) == 24
    assert len(d["weekdays"]) == 7
    assert "correlations" in d
    assert "coverage" in d
    r2 = client.get("/api/v1/insights?days=7", headers=h)
    assert r2.status_code == 200


def test_reports_export_csv():
    _, h = _new_user()
    client.post("/api/v1/events", json={"source": "test", "event_type": "foo.bar",
                                        "description": "hi"}, headers=h)
    r = client.get("/api/v1/reports/export?format=csv", headers=h)
    assert r.status_code == 200, r.text
    assert "text/csv" in r.headers.get("content-type", "")
    body = r.text
    assert body.splitlines()[0].startswith("id,timestamp,source")
    assert "foo.bar" in body
