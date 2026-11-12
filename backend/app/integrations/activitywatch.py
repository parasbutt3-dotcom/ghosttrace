import httpx
from datetime import datetime, timezone

from app.integrations.base import BaseIntegration, Capability
from app.integrations.registry import register


@register("activitywatch")
class ActivityWatchIntegration(BaseIntegration):
    kind = "activitywatch"
    display_name = "ActivityWatch"

    def _base_url(self):
        cfg = self.integration.config if self.integration else {}
        return (cfg or {}).get("base_url", "http://localhost:5600")

    def capabilities(self):
        return [
            Capability("buckets", True, "ActivityWatch exposes buckets via /api/0/buckets"),
            Capability("events", True, "Events via /api/0/buckets/{id}/events"),
            Capability("window_activity", True, "aw-watcher-window bucket"),
            Capability("web_activity", True, "aw-watcher-web bucket (if installed)"),
            Capability("afk_status", True, "aw-watcher-afk bucket"),
        ]

    async def sync(self):
        base = self._base_url()
        summary = {"ok": False, "events_created": 0, "buckets": []}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(f"{base}/api/0/buckets", timeout=10)
                if r.status_code != 200:
                    raise RuntimeError(f"AW buckets {r.status_code}: {r.text}")
                buckets = r.json()
                summary["buckets"] = list(buckets.keys())
                summary["ok"] = True
        except Exception as e:
            summary["error"] = str(e)
            if self.integration:
                self.integration.last_error = str(e)
                self.integration.status = "error"
                if self.db:
                    self.db.commit()
            return summary

        from app.services.events import ingest_event
        async with httpx.AsyncClient(timeout=30) as client:
            for bid, info in buckets.items():
                try:
                    r = await client.get(f"{base}/api/0/buckets/{bid}/events", params={"limit": 200})
                    if r.status_code != 200:
                        continue
                    events = r.json()
                    for ev in events:
                        data = ev.get("data", {}) or {}
                        ts = ev.get("timestamp")
                        try:
                            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else datetime.now(timezone.utc)
                        except Exception:
                            dt = datetime.now(timezone.utc)
                        app = data.get("app") or data.get("url") or bid
                        title = data.get("title") or data.get("$title") or ""
                        etype = "afk" if "afk" in bid else ("web.visit" if "web" in bid else "window.focus")
                        ingest_event(
                            self.db, self.user_id,
                            device_id=None, account_id=None, integration_kind="activitywatch",
                            source="activitywatch", application=app, event_type=etype,
                            category="activity", description=title or bid,
                            metadata={"bucket": bid, "duration": ev.get("duration"), "data": data},
                            collection_method="api", permission_status="authorized", confidence=1.0,
                            dedup_key=f"aw:{bid}:{ev.get('id', ts)}",
                            timestamp=dt,
                        )
                        summary["events_created"] += 1
                except Exception as e:
                    summary.setdefault("bucket_errors", {})[bid] = str(e)

        if self.integration:
            self.integration.last_sync_at = datetime.now(timezone.utc)
            self.integration.status = "ok" if summary["ok"] else "error"
            self.integration.last_error = summary.get("error")
            if self.db:
                self.db.commit()
        return summary