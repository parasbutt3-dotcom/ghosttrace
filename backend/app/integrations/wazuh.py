import httpx
from datetime import datetime, timezone

from app.integrations.base import BaseIntegration, Capability
from app.integrations.registry import register
from app.core.security import decrypt_secret
from app.config import settings


@register("wazuh")
class WazuhIntegration(BaseIntegration):
    kind = "wazuh"
    display_name = "Wazuh SIEM"

    def _cfg(self):
        return self.integration.config if self.integration else {}

    def _verify(self):
        if not settings.WAZUH_VERIFY_SSL:
            return False
        if settings.WAZUH_CA_BUNDLE:
            return settings.WAZUH_CA_BUNDLE
        return True

    async def _auth_token(self):
        cfg = self._cfg()
        base = cfg.get("base_url", "https://localhost:55000")
        user = cfg.get("username", "wazuh")
        pw = decrypt_secret(cfg.get("password_enc", "")) or cfg.get("password", "")
        try:
            async with httpx.AsyncClient(verify=self._verify(), timeout=15) as client:
                r = await client.post(f"{base}/security/user/authenticate", auth=(user, pw))
                if r.status_code == 200:
                    return base, r.json().get("data", {}).get("token")
        except Exception:
            pass
        return base, None

    def capabilities(self):
        return [
            Capability("agents", True, "List Wazuh agents"),
            Capability("alerts", True, "Recent alerts via /alerts"),
            Capability("vulnerabilities", False, "Requires vulnerability detector module", requires=["vulnerability-detector"]),
        ]

    async def sync(self):
        base, token = await self._auth_token()
        summary = {"ok": False, "events_created": 0}
        if not token:
            summary["error"] = "authentication failed"
            if self.integration:
                self.integration.last_error = summary["error"]; self.integration.status = "error"
                if self.db: self.db.commit()
            return summary
        headers = {"Authorization": f"Bearer {token}"}
        from app.services.events import ingest_event
        verify = self._verify()
        async with httpx.AsyncClient(verify=verify, timeout=30) as client:
            # agents
            try:
                r = await client.get(f"{base}/agents", headers=headers, params={"limit": 100})
                if r.status_code == 200:
                    for a in r.json().get("data", {}).get("affected_items", []):
                        ingest_event(
                            self.db, self.user_id, integration_kind="wazuh", source="wazuh",
                            application="Wazuh Agent", event_type="agent.status",
                            category="device", description=f"Agent {a.get('name')} ({a.get('status')})",
                            metadata={"agent": a}, collection_method="api", permission_status="authorized", confidence=1.0,
                            dedup_key=f"wazuh:agent:{a.get('id')}",
                        )
                        summary["events_created"] += 1
            except Exception as e:
                summary.setdefault("errors", []).append(str(e))
            # alerts
            try:
                r = await client.get(f"{base}/alerts", headers=headers, params={"limit": 100, "sort": "-timestamp"})
                if r.status_code == 200:
                    for al in r.json().get("data", {}).get("affected_items", []):
                        ts = al.get("timestamp")
                        try:
                            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else datetime.now(timezone.utc)
                        except Exception:
                            dt = datetime.now(timezone.utc)
                        ingest_event(
                            self.db, self.user_id, integration_kind="wazuh", source="wazuh",
                            application="Wazuh", event_type=f"alert.{al.get('rule', {}).get('level', '')}",
                            category="security", description=al.get("rule", {}).get("description", "alert"),
                            metadata={"alert": al}, collection_method="api", permission_status="authorized", confidence=1.0,
                            dedup_key=f"wazuh:alert:{al.get('id')}", timestamp=dt,
                        )
                        summary["events_created"] += 1
            except Exception as e:
                summary.setdefault("errors", []).append(str(e))

        summary["ok"] = True
        if self.integration:
            self.integration.last_sync_at = datetime.now(timezone.utc)
            self.integration.status = "ok"
            self.integration.last_error = None
            if self.db:
                self.db.commit()
        return summary
