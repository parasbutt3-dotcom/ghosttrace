import os
import uuid
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_ghosttrace.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32chars-minimum-aaaa")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "QFJ-zhAIHeDkTDc8kPgFgjHhMbDO6u6_gc5XSfw69oI=")
os.environ.setdefault("AUTO_SYNC_ENABLED", "false")

from unittest import mock
from fastapi.testclient import TestClient
from app.main import app
from app.api.v1.auth import limiter

limiter.enabled = False
client = TestClient(app)


def _register(email=None):
    email = email or f"ev_{uuid.uuid4().hex[:8]}@example.com"
    return email, client.post("/api/v1/auth/register", json={"email": email, "password": "pw123456"})


def test_verify_email_disabled_register_issues_tokens():
    from app.config import settings
    assert settings.EMAIL_VERIFY_ENABLED is False
    email, r = _register()
    assert r.status_code == 200, r.text
    assert r.json().get("access_token")
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=h).status_code == 200


def test_verify_email_flow_enabled():
    from app.config import settings
    import smtplib

    class FakeSMTP:
        instances = []

        def __init__(self, host, port):
            self.host = host
            self.port = port
            self.sent = []
            FakeSMTP.instances.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            pass

        def login(self, u, p):
            pass

        def send_message(self, msg):
            self.sent.append(msg)

    FakeSMTP.instances = []
    with mock.patch.object(settings, "EMAIL_VERIFY_ENABLED", True), \
            mock.patch.object(smtplib, "SMTP", FakeSMTP):
        email, r = _register()
        assert r.status_code == 200, r.text
        # Restricted state: no live tokens at registration.
        assert not r.json().get("access_token")

        # Unverified login is blocked.
        lr = client.post("/api/v1/auth/login", json={"email": email, "password": "pw123456"})
        assert lr.status_code == 403, lr.text
        assert lr.json()["detail"] == "email not verified"

        # Token persisted on the user row.
        from app.database import SessionLocal
        from app.models.user import User
        db = SessionLocal()
        try:
            u = db.query(User).filter(User.email == email).first()
            assert u is not None
            assert u.email_verified is False
            token = (u.email_verification_token or u.email_verify_token
                     or u.verify_email_token or u.verification_token)
            assert token
        finally:
            db.close()

        # Verification email attempted via smtplib.
        assert len(FakeSMTP.instances) >= 1
        assert any(inst.sent for inst in FakeSMTP.instances)

        # Verify endpoint accepts the token and issues tokens.
        vr = client.post("/api/v1/auth/verify-email", json={"token": token})
        assert vr.status_code == 200, vr.text

        # Now login works.
        lr2 = client.post("/api/v1/auth/login", json={"email": email, "password": "pw123456"})
        assert lr2.status_code == 200, lr2.text
        assert lr2.json().get("access_token")


def test_verify_email_invalid_token():
    from app.config import settings
    with mock.patch.object(settings, "EMAIL_VERIFY_ENABLED", True):
        r = client.post("/api/v1/auth/verify-email", json={"token": "not-a-real-token"})
        assert r.status_code == 400