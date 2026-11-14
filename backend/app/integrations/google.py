import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import settings
from app.core.security import decrypt_secret, encrypt_secret, ensure_utc
from app.integrations.base import BaseIntegration, Capability
from app.integrations.registry import register

logger = logging.getLogger("ghosttrace.integrations.google")

GMAIL_ALERT_SENDER = "no-reply@accounts.google.com"

_ALERT_PATTERNS = [
    (("new sign-in", "sign-in to your google account", "unusual sign-in", "unusual activity", "a new device signed in"),
     "security.login_alert", "New sign-in / activity alert"),
    (("password", "passkey"), "security.password_change", "Credential change"),
    (("recovery email", "recovery phone", "recovery option"), "security.recovery_change", "Recovery option change"),
    (("2-step", "two-step", "verification prompt", "authenticator"), "security.mfa_change", "2-Step Verification change"),
    (("security alert", "important security"), "security.alert", "Google security alert"),
]


def classify_google_alert(subject: str) -> tuple[str, str] | None:
    s = (subject or "").lower()
    if not s:
        return None
    for needles, event_type, label in _ALERT_PATTERNS:
        if any(n in s for n in needles):
            return event_type, label
    return None


_DEVICE_WORDS = {
    "iphone": "iPhone", "ipad": "iPad", "android": "Android", "windows": "Windows",
    "chrome os": "ChromeOS", "chromebook": "Chromebook", "mac": "Mac",
    "linux": "Linux", "playstation": "PlayStation", "xbox": "Xbox",
}


def parse_alert_details(text: str) -> dict:
    """Extract device / location / IP hints from alert subject+snippet so phone
    sign-ins are attributable without any on-device agent."""
    out: dict[str, str] = {}
    lower = (text or "").lower()
    # Longest keys first so "chrome os" wins over "mac" inside "chrome mac..." noise
    for word, label in sorted(_DEVICE_WORDS.items(), key=lambda kv: -len(kv[0])):
        if word in lower:
            out["device"] = label
            break
    m = re.search(r"(?:near|in|from) ([A-Z][A-Za-z '-]*, [A-Z][A-Za-z '-]*)", text or "")
    if m:
        out["location"] = m.group(1).strip()
    m = re.search(r"\bIP(?: address)?[:\s]+((?:\d{1,3}\.){3}\d{1,3})", text or "", re.I)
    if m:
        out["ip"] = m.group(1)
    return out


def _rfc2822_to_datetime(value: str):
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


@register("google")
class GoogleIntegration(BaseIntegration):
    kind = "google"
    display_name = "Google Account"

    def _token(self) -> str:
        if not self.account:
            return ""
        return decrypt_secret(self.account.access_token_enc or "")

    async def _refresh_if_needed(self):
        if not self.account:
            return
        exp = ensure_utc(self.account.token_expires_at)
        if exp and exp > datetime.now(timezone.utc):
            return
        rt = decrypt_secret(self.account.refresh_token_enc or "")
        if not rt or not settings.GOOGLE_CLIENT_ID:
            return
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": settings.GOOGLE_CLIENT_ID,
                        "client_secret": settings.GOOGLE_CLIENT_SECRET,
                        "refresh_token": rt,
                        "grant_type": "refresh_token",
                    },
                )
            if r.status_code == 200:
                d = r.json()
                self.account.access_token_enc = encrypt_secret(d.get("access_token", ""))
                if d.get("expires_in"):
                    self.account.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=d["expires_in"])
                self.account.status = "connected"
            else:
                logger.warning("google refresh rejected for account %s: %s", self.account.id, r.text)
                self.account.status = "expired"
            if self.db:
                self.db.commit()
        except httpx.HTTPError as e:
            logger.warning("google refresh failed: %s", e)

    def _scopes(self):
        return self.account.scopes if self.account else []

    def capabilities(self):
        scopes = self._scopes() or []
        admin_reports = any("admin.reports" in s for s in scopes)
        gmail_readonly = any("gmail.readonly" in s for s in scopes)
        calendar_readonly = any("calendar.readonly" in s for s in scopes)
        drive_readonly = any("drive.readonly" in s for s in scopes)
        return [
            Capability("calendar_events", calendar_readonly,
                       "Upcoming calendar events (title/time only) sync into the timeline." if calendar_readonly
                       else "Not consented. Reconnect with the Calendar option to see meetings alongside activity.",
                       requires=["https://www.googleapis.com/auth/calendar.readonly"] if not calendar_readonly else []),
            Capability("drive_recent_files", drive_readonly,
                       "Recently modified file names sync as activity (no file contents)." if drive_readonly
                       else "Not consented. Reconnect with the Drive option to track file work.",
                       requires=["https://www.googleapis.com/auth/drive.readonly"] if not drive_readonly else []),
            Capability("account_identity", True, "Available via OpenID Connect userinfo"),
            Capability("granted_scopes", True, "Scopes returned by token exchange"),
            Capability("token_status", True, "Token expiry tracked locally"),
            Capability("connected_applications_inventory", admin_reports,
                       "No consumer API exposes the third-party app list. Review grants manually at https://myaccount.google.com/permissions — "
                       "automated inventory requires the Google Workspace Admin SDK."
                       if not admin_reports else
                       "Available via Google Workspace Admin SDK for managed domains."),
            Capability("login_security_events", admin_reports or gmail_readonly,
                       "Google Workspace Reports API (admin) provides login events for managed domains." if admin_reports
                       else ("Ingested from Google security-alert emails (sign-ins, password/recovery/MFA changes) via gmail.readonly consent."
                             if gmail_readonly
                             else "Consumer accounts have no Reports API, but alerts can be derived from Gmail security emails — reconnect with the Gmail-alert option."),
                       requires=[] if (admin_reports or gmail_readonly) else ["https://www.googleapis.com/auth/gmail.readonly"]),
            Capability("gmail_activity", gmail_readonly,
                       "gmail.readonly consent granted — security-alert ingestion enabled; mailbox contents are not stored."
                       if gmail_readonly else "Not consented. Use 'Connect Google (with Gmail alerts)' to allow read-only access.",
                       requires=["https://www.googleapis.com/auth/gmail.readonly"] if not gmail_readonly else []),
            Capability("device_location", False, "Google does not expose device GPS/location to third parties."),
        ]

    async def sync(self):
        await self._refresh_if_needed()
        token = self._token()
        if not token:
            return {"ok": False, "error": "no token"}
        summary: dict[str, Any] = {"ok": True, "events_created": 0, "capabilities": [c.to_dict() for c in self.capabilities()]}
        async with httpx.AsyncClient(timeout=30) as client:
            # 1. userinfo
            try:
                r = await client.get("https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": f"Bearer {token}"})
                if r.status_code == 200:
                    ui = r.json()
                    self._ingest_event(
                        source="google", application="Google Account", event_type="account.identity",
                        category="account", description=f"Account identity verified: {ui.get('email')}",
                        metadata={"userinfo": ui}, collection_method="oauth_api", permission_status="authorized", confidence=1.0,
                        dedup_key=f"google:identity:{ui.get('sub')}",
                    )
                    summary["events_created"] += 1
                else:
                    summary["userinfo_status"] = r.status_code
            except Exception as e:
                summary["userinfo_error"] = str(e)

            # 2. tokeninfo
            try:
                r = await client.get(f"https://oauth2.googleapis.com/tokeninfo?access_token={token}")
                if r.status_code == 200:
                    ti = r.json()
                    self._ingest_event(
                        source="google", application="Google OAuth", event_type="token.scopes",
                        category="security", description=f"Granted scopes: {ti.get('scope')}",
                        metadata={"tokeninfo": ti}, collection_method="oauth_api", permission_status="authorized", confidence=1.0,
                        dedup_key=f"google:scopes:{ti.get('sub')}",
                    )
                    summary["events_created"] += 1
                    if self.account:
                        self.account.scopes = ti.get("scope", "").split()
                        if self.db:
                            self.db.commit()
            except Exception as e:
                summary["tokeninfo_error"] = str(e)

            # 3. Google Workspace admin reports
            if any("admin.reports" in s for s in (self.account.scopes or [])):
                try:
                    r = await client.get(
                        "https://admin.googleapis.com/admin/reports/v1/activity/users/all/applications/login",
                        headers={"Authorization": f"Bearer {token}"},
                        params={"maxResults": 50},
                    )
                    if r.status_code == 200:
                        for item in r.json().get("items", []):
                            self._ingest_event(
                                source="google", application="Google Workspace", event_type="login.event",
                                category="security", description=f"Login event: {item.get('events', [{}])[0].get('name', '')}",
                                metadata={"report": item}, collection_method="oauth_api",
                                permission_status="authorized", confidence=1.0,
                                dedup_key=f"google:login:{item.get('id', {}).get('uniqueQualifier')}",
                            )
                            summary["events_created"] += 1
                except Exception as e:
                    summary["reports_error"] = str(e)

            # 3b. Calendar events (next 7 days + past 24h)
            if any("calendar.readonly" in s for s in (self.account.scopes or [])):
                try:
                    time_min = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat().replace("+00:00", "Z")
                    time_max = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat().replace("+00:00", "Z")
                    r = await client.get(
                        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                        headers={"Authorization": f"Bearer {token}"},
                        params={"timeMin": time_min, "timeMax": time_max, "maxResults": 50, "singleEvents": "true"},
                    )
                    count = 0
                    if r.status_code == 200:
                        for ev in r.json().get("items", []):
                            start = (ev.get("start") or {}).get("dateTime") or (ev.get("start") or {}).get("date")
                            self._ingest_event(
                                source="google", application="Google Calendar", event_type="calendar.event",
                                category="calendar", description=f"Event: {ev.get('summary') or 'Untitled'}",
                                timestamp=start,
                                metadata={"calendar_event_id": ev.get("id"), "summary": ev.get("summary"),
                                          "start": ev.get("start"), "end": ev.get("end"), "location": ev.get("location")},
                                collection_method="oauth_api", permission_status="authorized", confidence=1.0,
                                dedup_key=f"google:calendar:{ev.get('id')}",
                            )
                            count += 1
                        summary["calendar_events_ingested"] = count
                    else:
                        summary["calendar_status"] = r.status_code
                except Exception as e:
                    summary["calendar_error"] = str(e)

            # 3c. Drive recent files (names only, privacy-safe)
            if any("drive.readonly" in s for s in (self.account.scopes or [])):
                try:
                    r = await client.get(
                        "https://www.googleapis.com/drive/v3/files",
                        headers={"Authorization": f"Bearer {token}"},
                        params={"pageSize": 25, "orderBy": "modifiedTime desc", "fields": "files(id,name,mimeType,modifiedTime)"},
                    )
                    if r.status_code == 200:
                        for f in r.json().get("files", []):
                            self._ingest_event(
                                source="google", application="Google Drive", event_type="drive.file_modified",
                                category="work", description=f"Modified: {f.get('name')}",
                                timestamp=f.get("modifiedTime"),
                                metadata={"drive_file_id": f.get("id"), "name": f.get("name"), "mime_type": f.get("mimeType")},
                                collection_method="oauth_api", permission_status="authorized", confidence=1.0,
                                dedup_key=f"google:drive:{f.get('id')}:{f.get('modifiedTime')}",
                            )
                        summary["drive_files_ingested"] = len(r.json().get("files", []))
                    else:
                        summary["drive_status"] = r.status_code
                except Exception as e:
                    summary["drive_error"] = str(e)

            # 4. Gmail alerts
            if any("gmail.readonly" in s for s in (self.account.scopes or [])):
                try:
                    res = await self._ingest_gmail_alerts(client, token)
                    if res >= 0:
                        summary["gmail_alerts_ingested"] = res
                    else:
                        summary["gmail_alerts_status"] = "rejected_by_gmail_api"
                except Exception as e:
                    summary["gmail_alerts_error"] = str(e)

        # 5. gap tracking
        scopes_now = self.account.scopes or []
        gaps = {}
        if not any("admin.reports" in s for s in scopes_now):
            gaps["connected_applications_inventory"] = "no consumer API; review https://myaccount.google.com/permissions manually"
        if not any("admin.reports" in s for s in scopes_now) and not any("gmail.readonly" in s for s in scopes_now):
            gaps["login_security_events"] = "reconnect via 'Connect Google (with Gmail alerts)' to derive login/security events from Gmail"
        if gaps:
            self._ingest_event(
                source="google", application="Google Account", event_type="capability.inventory",
                category="meta",
                description="Automatable gaps for this account: " + "; ".join(f"{k}: {v}" for k, v in gaps.items()),
                metadata={"gaps": gaps, "permission_status": "unavailable"},
                collection_method="oauth_api", permission_status="unavailable", confidence=0.0,
                dedup_key="google:capability:connected_apps",
            )

        if self.integration:
            self.integration.last_sync_at = datetime.now(timezone.utc)
            self.integration.status = "ok"
            self.integration.last_error = None
            if self.db:
                self.db.commit()
        return summary

    async def _ingest_gmail_alerts(self, client: httpx.AsyncClient, token: str) -> int:
        auth = {"Authorization": f"Bearer {token}"}
        base = "https://gmail.googleapis.com/gmail/v1/users/me"
        r = await client.get(f"{base}/messages", headers=auth, params={"q": f"from:{GMAIL_ALERT_SENDER}", "maxResults": 50})
        if r.status_code != 200:
            logger.warning("gmail alert list failed: %s %s", r.status_code, r.text[:200])
            return -1
        ids = [m.get("id") for m in r.json().get("messages", []) if m.get("id")]
        ingested = 0
        for mid in ids:
            mr = await client.get(f"{base}/messages/{mid}", headers=auth, params={"format": "metadata", "metadataHeaders": ["Subject", "Date"]})
            if mr.status_code != 200:
                continue
            mdata = mr.json()
            headers = {h.get("name", "").lower(): h.get("value", "") for h in mdata.get("payload", {}).get("headers", [])}
            subject = headers.get("subject", "")
            parsed = classify_google_alert(subject)
            if not parsed:
                continue
            event_type, label = parsed
            details = parse_alert_details(f"{subject} {mdata.get('snippet', '')}")
            desc = f"{label}: {subject}"
            if details:
                desc += " [" + " · ".join(details.get(k, "") for k in ("device", "location", "ip") if details.get(k)) + "]"
            self._ingest_event(
                source="google", application="Google Security Alerts", event_type=event_type,
                category="security",
                description=desc,
                timestamp=_rfc2822_to_datetime(headers.get("date", "")),
                metadata={"gmail_message_id": mid, "subject": subject, "date": headers.get("date", ""), **details},
                collection_method="gmail_alerts", permission_status="authorized", confidence=0.9,
                dedup_key=f"google:alert:{mid}",
            )
            ingested += 1
        return ingested

    def _ingest_event(self, **kw):
        if not self.db:
            return
        from app.services.events import ingest_event
        ingest_event(self.db, self.user_id, account_id=self.account.id if self.account else None,
                     integration_kind="google", **kw)