import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_ghosttrace.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32chars-minimum-aaaa")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "QFJ-zhAIHeDkTDc8kPgFgjHhMbDO6u6_gc5XSfw69oI=")
# Keep the background sync loop off in tests; it would hit real Google/Gmail endpoints.
os.environ.setdefault("AUTO_SYNC_ENABLED", "false")

import uuid
from unittest import mock

import httpx
from fastapi.testclient import TestClient
from app.main import app
from app.api.v1.auth import limiter

# Test client hits the limiter as a single "testclient" IP; skip rate-limit checks in tests.
limiter.enabled = False

client = TestClient(app)


def _new_user(email=None):
    email = email or f"u_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "pw123456"})
    assert r.status_code == 200, r.text
    return email, {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_register_login():
    email, h = _new_user()
    r2 = client.get("/api/v1/auth/me", headers=h)
    assert r2.status_code == 200
    assert r2.json()["email"] == email


def test_event_ingest_and_list():
    _, h = _new_user()
    r = client.post("/api/v1/events", json={"source": "test", "event_type": "foo.bar", "description": "hi"}, headers=h)
    assert r.status_code == 200
    r = client.get("/api/v1/events", headers=h)
    assert r.status_code == 200
    assert r.json()["total"] >= 1
    r = client.get("/api/v1/events/stats", headers=h)
    assert r.status_code == 200


def _fake_google_responses(sub, email):
    tok = httpx.Response(
        200,
        json={
            "access_token": "ya29.fake",
            "refresh_token": "rt.fake",
            # Google really returns expires_in as a string — must not crash on it.
            "expires_in": "3600",
            "scope": "openid email profile",
            "token_type": "Bearer",
        },
        request=httpx.Request("POST", "https://oauth2.googleapis.com/token"),
    )
    ui = httpx.Response(
        200,
        json={"sub": sub, "name": "Test User", "email": email},
        request=httpx.Request("GET", "https://openidconnect.googleapis.com/v1/userinfo"),
    )
    return mock.patch("httpx.post", return_value=tok), mock.patch("httpx.get", return_value=ui)


def test_google_oauth_callback_success():
    from app.database import SessionLocal
    from app.models.account import ConnectedAccount
    from app.models.integration import Integration

    email, h = _new_user()
    sub = f"google-sub-{uuid.uuid4().hex[:8]}"
    state = client.get("/api/v1/auth/google/login", headers=h).json()["state"]

    p1, p2 = _fake_google_responses(sub, email)
    with p1, p2:
        r = client.get("/api/v1/auth/google/callback", params={"code": "4/0fake", "state": state}, follow_redirects=False)
    assert r.status_code in (302, 307), r.text
    assert "connected=google" in r.headers["location"]

    db = SessionLocal()
    try:
        acct = db.query(ConnectedAccount).filter(
            ConnectedAccount.provider == "google", ConnectedAccount.email == email
        ).first()
        assert acct and acct.status == "connected" and acct.provider_account_id == sub
        assert acct.token_expires_at is not None
        integ = db.query(Integration).filter(Integration.user_id == acct.user_id, Integration.kind == "google").first()
        # Regression: Integration must actually link the account (needs a flush before acct.id is read).
        assert integ and integ.account_id == acct.id
    finally:
        db.close()

    # State must be single-use: replaying it must not connect again, just redirect with an error.
    p1, p2 = _fake_google_responses(sub, email)
    with p1, p2:
        r2 = client.get("/api/v1/auth/google/callback", params={"code": "4/0fake", "state": state}, follow_redirects=False)
    assert r2.status_code in (302, 307)
    assert "error=invalid_or_expired_state" in r2.headers["location"]


def test_google_oauth_cross_link_guard():
    from app.database import SessionLocal
    from app.models.account import ConnectedAccount

    email, h = _new_user()
    sub = f"google-sub-{uuid.uuid4().hex[:8]}"
    p1, p2 = _fake_google_responses(sub, email)
    state = client.get("/api/v1/auth/google/login", headers=h).json()["state"]
    with p1, p2:
        assert client.get("/api/v1/auth/google/callback", params={"code": "x", "state": state}, follow_redirects=False).status_code in (302, 307)

    # Second user tries to link the same Google identity.
    _, h2 = _new_user()
    state2 = client.get("/api/v1/auth/google/login", headers=h2).json()["state"]
    p1, p2 = _fake_google_responses(sub, email)
    with p1, p2:
        r = client.get("/api/v1/auth/google/callback", params={"code": "x", "state": state2}, follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "error=account_already_linked" in r.headers["location"]

    db = SessionLocal()
    try:
        assert db.query(ConnectedAccount).filter(
            ConnectedAccount.provider == "google", ConnectedAccount.provider_account_id == sub
        ).count() == 1
    finally:
        db.close()


def test_classify_google_alert():
    from app.integrations.google import classify_google_alert
    assert classify_google_alert("New sign-in to your Google Account")[0] == "security.login_alert"
    assert classify_google_alert("A new sign-in on Windows")[0] == "security.login_alert"
    assert classify_google_alert("Your password was changed recently")[0] == "security.password_change"
    assert classify_google_alert("Your recovery email was changed")[0] == "security.recovery_change"
    assert classify_google_alert("Security alert")[0] == "security.alert"
    assert classify_google_alert("Your flight to Paris") is None
    assert classify_google_alert("") is None


def test_google_capabilities_gmail_path():
    from types import SimpleNamespace
    from app.integrations.google import GoogleIntegration

    def caps(scopes):
        acct = SimpleNamespace(scopes=scopes)
        return {c.name: c for c in GoogleIntegration(user_id="u", account=acct, integration=None, db=None).capabilities()}

    c = caps(["openid", "email", "profile"])
    assert c["login_security_events"].available is False
    assert c["connected_applications_inventory"].available is False

    c = caps(["openid", "https://www.googleapis.com/auth/gmail.readonly"])
    assert c["login_security_events"].available is True
    assert c["gmail_activity"].available is True
    # consumer app inventory stays honestly unavailable
    assert c["connected_applications_inventory"].available is False


def test_google_sync_ingests_gmail_alerts():
    import asyncio
    from types import SimpleNamespace
    from datetime import datetime, timezone, timedelta
    from unittest.mock import patch
    import httpx as httpx_lib
    from app.core.security import encrypt_secret
    from app.integrations.google import GoogleIntegration

    acct = SimpleNamespace(
        id="acct-1", scopes=["openid", "https://www.googleapis.com/auth/gmail.readonly"],
        access_token_enc=encrypt_secret("tok"), refresh_token_enc="", token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    integ = GoogleIntegration(user_id="u1", account=acct, integration=None, db=None)

    def resp(url, payload):
        return httpx_lib.Response(200, json=payload, request=httpx_lib.Request("GET", url))

    msgs = {"https://gmail.googleapis.com/gmail/v1/users/me/messages": {"messages": [{"id": "m1"}, {"id": "m2"}, {"id": "m3"}]}}

    def fake_get(url, **kw):
        if "userinfo" in url:
            return resp(url, {"sub": "g1", "email": "x@example.com"})
        if "tokeninfo" in url:
            return resp(url, {"sub": "g1", "scope": "openid https://www.googleapis.com/auth/gmail.readonly"})
        if url.endswith("/messages"):
            return resp(url, msgs[url])
        hdr_map = {
            "m1": ("New sign-in to your Google Account", "Tue, 10 Nov 2026 20:00:00 GMT"),
            "m2": ("Your Google Play receipt", "Tue, 10 Nov 2026 19:00:00 GMT"),
            "m3": ("A new sign-in on a Windows device", "Mon, 09 Nov 2026 12:00:00 GMT"),
        }
        mid = url.rsplit("/", 1)[-1]
        subj, date = hdr_map[mid]
        return resp(url, {"id": mid, "payload": {"headers": [{"name": "Subject", "value": subj}, {"name": "Date", "value": date}]}})

    class _FakeAsyncClient:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def get(self, url, **kw):
            return fake_get(url, **kw)
        async def post(self, url, **kw):
            return fake_get(url, **kw)

    with patch("httpx.AsyncClient", _FakeAsyncClient):
        summary = asyncio.run(integ.sync())

    assert summary["ok"] is True
    assert summary["gmail_alerts_ingested"] == 2
    assert "gmail_alerts_error" not in summary


def test_logout_all_revokes_everything():
    email = f"la_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "pw123456"})
    assert r.status_code == 200
    tok = r.json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=h).status_code == 200

    assert client.post("/api/v1/auth/logout-all", headers=h).status_code == 200

    # Tokens minted before the cutoff are dead — access, refresh alike.
    assert client.get("/api/v1/auth/me", headers=h).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": tok["refresh_token"]}).status_code == 401

    # A fresh login after logout-all works again. iat has 1s granularity, so wait
    # until the next second for the new token to clear the cutoff (by design).
    import time
    time.sleep(1.1)
    r2 = client.post("/api/v1/auth/login", json={"email": email, "password": "pw123456"})
    assert r2.status_code == 200, r2.text
    h2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=h2).status_code == 200
    # and rotating a refresh still functions after the cutoff
    r3 = client.post("/api/v1/auth/refresh", json={"refresh_token": r2.json()["refresh_token"]})
    assert r3.status_code == 200


def test_google_callback_expired_state_redirects():
    # The exact scenario that used to 500: state row exists with a naive-looking
    # expiry, callback must redirect cleanly instead of crashing.
    from app.database import SessionLocal
    from app.models.oauth_state import OAuthState
    from datetime import datetime, timezone, timedelta

    email, h = _new_user()
    uid = client.get("/api/v1/auth/me", headers=h).json()["id"]
    st = f"expired-{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        db.add(OAuthState(user_id=uid, provider="google", state=st,
                          code_verifier="v", redirect_uri="http://localhost:8000/api/v1/auth/google/callback",
                          expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
        db.commit()
    finally:
        db.close()
    r = client.get("/api/v1/auth/google/callback", params={"code": "x", "state": st}, follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "error=invalid_or_expired_state" in r.headers["location"]


def test_change_password_invalidates_sessions():
    email = f"cp_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "pw123456"})
    tok = r.json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    # Wrong current password rejected
    bad = client.post("/api/v1/auth/change-password", json={"current_password": "wrongpw123", "new_password": "newpw12345"}, headers=h)
    assert bad.status_code == 401
    ok = client.post("/api/v1/auth/change-password", json={"current_password": "pw123456", "new_password": "newpw12345"}, headers=h)
    assert ok.status_code == 200
    # Old sessions dead
    assert client.get("/api/v1/auth/me", headers=h).status_code == 401
    import time
    time.sleep(1.1)
    assert client.post("/api/v1/auth/login", json={"email": email, "password": "pw123456"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": email, "password": "newpw12345"}).status_code == 200


def test_delete_account_purges_data():
    from app.database import SessionLocal
    from app.models.user import User
    from app.models.event import Event

    email = f"del_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "pw123456"})
    tok = r.json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    client.post("/api/v1/events", json={"source": "test", "event_type": "foo.bar", "description": "hi"}, headers=h)
    uid = client.get("/api/v1/auth/me", headers=h).json()["id"]

    bad = client.request("DELETE", "/api/v1/auth/account", json={"password": "wrongpw123"}, headers=h)
    assert bad.status_code == 401
    ok = client.request("DELETE", "/api/v1/auth/account", json={"password": "pw123456"}, headers=h)
    assert ok.status_code == 200

    db = SessionLocal()
    try:
        assert db.get(User, uid) is None
        assert db.query(Event).filter(Event.user_id == uid).count() == 0
    finally:
        db.close()
    assert client.get("/api/v1/auth/me", headers=h).status_code == 401


def test_mfa_recovery_code_single_use():
    import pyotp
    email = f"rc_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "pw123456"})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    setup = client.post("/api/v1/auth/mfa/setup", headers=h)
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    codes = setup.json()["recovery_codes"]
    assert len(codes) == 10

    v = client.post("/api/v1/auth/mfa/verify", params={"code": pyotp.TOTP(secret).now()}, headers=h)
    assert v.status_code == 200

    # Login now requires MFA; authenticate with a recovery code.
    lr = client.post("/api/v1/auth/login", json={"email": email, "password": "pw123456"})
    assert lr.status_code == 200 and lr.json().get("mfa_required") is True
    mfa_token = lr.json()["mfa_token"]

    first = client.post("/api/v1/auth/mfa/login", params={"mfa_token": mfa_token, "code": codes[0]})
    assert first.status_code == 200
    # Replay of the same recovery code must fail.
    lr2 = client.post("/api/v1/auth/login", json={"email": email, "password": "pw123456"})
    second = client.post("/api/v1/auth/mfa/login", params={"mfa_token": lr2.json()["mfa_token"], "code": codes[0]})
    assert second.status_code == 401
    # A fresh unused code still works.
    third = client.post("/api/v1/auth/mfa/login", params={"mfa_token": lr2.json()["mfa_token"], "code": codes[1]})
    assert third.status_code == 200


def test_telemetry_rejects_invalid_battery():
    from app.database import SessionLocal
    from app.models.device import Device
    _, h = _new_user()
    r = client.post("/api/v1/devices/register", params={"name": "Pixel"}, headers=h)
    raw_key = r.json()["device_key"]
    # battery_level > 100 must be rejected
    bad = client.post("/api/v1/devices/telemetry", json={"battery_level": 150}, headers={"X-Device-Key": raw_key})
    assert bad.status_code == 422
    good = client.post("/api/v1/devices/telemetry",
                       json={"battery_level": 80, "events": [{"application": "Chrome", "event_type": "usage", "description": "browsing"}]},
                       headers={"X-Device-Key": raw_key})
    assert good.status_code == 200
    events = client.get("/api/v1/events", headers=h).json()
    assert events["total"] >= 2
    # Pagination metadata present
    assert events["limit"] == 100 and events["offset"] == 0


def test_api_key_lifecycle():
    _, h = _new_user()
    # Create API key
    r = client.post("/api/v1/apikeys", json={"name": "ci"}, headers=h)
    assert r.status_code == 200, r.text
    full_key = r.json()["key"]
    assert full_key.startswith("gt_")
    # Use API key as bearer to list events
    ah = {"Authorization": f"Bearer {full_key}"}
    r = client.get("/api/v1/events", headers=ah)
    assert r.status_code == 200
    # Ingest an event with API key
    r = client.post("/api/v1/events", json={"source": "apitest", "event_type": "x.y", "description": "d"}, headers=ah)
    assert r.status_code == 200
    # List keys
    r = client.get("/api/v1/apikeys", headers=h)
    assert r.status_code == 200
    kid = r.json()[0]["id"]
    # Revoke
    r = client.delete(f"/api/v1/apikeys/{kid}", headers=h)
    assert r.status_code == 200
    # Revoked key no longer works
    r = client.get("/api/v1/events", headers=ah)
    assert r.status_code == 401


def test_sessions_list_and_revoke():
    email = f"sess_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "pw123456"})
    tok = r.json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    # A login session is recorded
    r = client.get("/api/v1/auth/sessions", headers=h)
    assert r.status_code == 200
    sessions = r.json()["sessions"]
    assert len(sessions) >= 1
    cur = [s for s in sessions if s["current"]]
    assert len(cur) == 1
    # Revoke current session => its access token dies immediately
    r = client.post(f"/api/v1/auth/sessions/{cur[0]['id']}/revoke", headers=h)
    assert r.status_code == 200
    r = client.get("/api/v1/auth/me", headers=h)
    assert r.status_code == 401


def test_detection_rules_alert():
    _, h = _new_user()
    # Create a rule: category=work in 24h >= 1 => alert
    r = client.post("/api/v1/rules", json={"name": "work activity", "category": "work",
                                           "window_hours": 24, "min_count": 1, "severity": "low"}, headers=h)
    assert r.status_code == 200, r.text
    rule_id = r.json()["id"]
    # Seed a matching event
    client.post("/api/v1/events", json={"source": "test", "event_type": "git.push",
                                        "category": "work", "description": "push"}, headers=h)
    alerts = client.get("/api/v1/security/alerts", headers=h).json()["alerts"]
    types = [a["type"] for a in alerts]
    assert "detection_rule" in types
    assert any(a.get("resource_id") == rule_id for a in alerts)
    # Rule validation rejects filter-less rules
    r = client.post("/api/v1/rules", json={"name": "bad", "min_count": 1}, headers=h)
    assert r.status_code == 422
    # Delete
    r = client.delete(f"/api/v1/rules/{rule_id}", headers=h)
    assert r.status_code == 200


def test_github_integration_sync():
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import patch
    from app.integrations.github import GitHubIntegration

    integ = SimpleNamespace(config={"username": "octocat"}, id="i1")
    gh = GitHubIntegration(user_id="u9", account=None, integration=integ, db=None)

    events_payload = [
        {"id": "1", "type": "PushEvent", "created_at": "2026-11-10T12:00:00Z",
         "repo": {"name": "octocat/hello"}, "payload": {"commits": [{}, {}]}},
        {"id": "2", "type": "WatchEvent", "created_at": "2026-11-11T09:00:00Z",
         "repo": {"name": "some/project"}, "payload": {"action": "started"}},
    ]

    class FakeClient:
        def __init__(self, *a, **kw):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def get(self, url, **kw):
            import httpx as _h
            if "events" in url:
                return _h.Response(200, json=events_payload, request=_h.Request("GET", url))
            return _h.Response(404, json={}, request=_h.Request("GET", url))

    ingested = []
    with patch("httpx.AsyncClient", FakeClient), patch("app.services.events.ingest_event",
                                                        side_effect=lambda db, uid, **kw: ingested.append(kw) or SimpleNamespace(id="e")):
        summary = asyncio.run(gh.sync())
    assert summary["ok"] is True
    assert summary["events_created"] == 2
    assert {e["event_type"] for e in ingested} == {"git.push", "git.star"}


def _make_takeout_zip() -> bytes:
    import io, zipfile, json
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Takeout/Location History/Records.json", json.dumps({
            "locations": [
                {"timestampMs": "1731370000000", "latitudeE7": 515000000, "longitudeE7": -1000000, "accuracy": 10},
                {"timestampMs": "1731373600000", "latitudeE7": 515100000, "longitudeE7": -1001000, "accuracy": 15},
            ]}))
        zf.writestr("Takeout/Location History/SemanticLocationHistory.json", json.dumps({
            "placements": [{
                "startTimestampMs": "1731370000000", "endTimestampMs": "1731373600000", "placeId": "ChIJtest",
                "placeAttendances": [{
                    "location": {"latLng": {"latitude": 515000000, "longitude": -1000000},
                                 "locationContextConfidenceLocations": [{"confidence": 80}]},
                    "structuredAttribution": {"center": {"name": "Home"}}}]}]}))
        zf.writestr("Takeout/My Activity/Search/Google Search.json", json.dumps([
            {"title": "Searched for ghosttrace", "time": "2026-11-11T10:00:00Z", "products": ["Search"]}]))
        zf.writestr("Takeout/YouTube and YouTube Music/history/history-and-search-activity.json", json.dumps({
            "items": [{"header": "YouTube", "title": "Watched video",
                       "creationTimestamp": "2026-11-11T12:00:00Z",
                       "details": [{"name": "Name", "value": "cool video"}]}]}))
    return buf.getvalue()


def test_takeout_import_and_dedup():
    _, h = _new_user()
    data = _make_takeout_zip()
    r = client.post("/api/v1/takeout/import", files={"file": ("takeout.zip", data, "application/zip")}, headers=h)
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["ok"] is True
    assert s["locations"] == 2 and s["place_visits"] == 1 and s["activities"] == 1 and s["youtube"] == 1
    # Re-import: dedup keys prevent duplicates
    r2 = client.post("/api/v1/takeout/import", files={"file": ("takeout.zip", data, "application/zip")}, headers=h)
    assert r2.status_code == 200
    ev = client.get("/api/v1/events?source=google_takeout", headers=h).json()
    assert ev["total"] == 5  # 2+1+1+1, not 10
    # Location events carry coordinates usable for mapping
    pts = [e for e in ev["items"] if e["event_type"] == "location.point"]
    assert all("latitude" in (e["metadata"] or {}) for e in pts)
    # Bad upload rejected
    bad = client.post("/api/v1/takeout/import", files={"file": ("x.txt", b"not a zip", "text/plain")}, headers=h)
    assert bad.status_code == 422


def test_health_security_headers():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("referrer-policy") == "no-referrer"
    csp = r.headers.get("content-security-policy", "")
    assert "default-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    # HSTS is only sent in production; test env is development.
    assert "strict-transport-security" not in r.headers
