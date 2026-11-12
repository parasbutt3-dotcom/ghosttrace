from app.integrations.base import BaseIntegration, Capability
from app.integrations.registry import register
from datetime import datetime, timezone


@register("android")
class AndroidIntegration(BaseIntegration):
    kind = "android"
    display_name = "Android Companion"

    def capabilities(self):
        return [
            Capability("device_registration", True, "Devices register with a device key"),
            Capability("app_usage_stats", True, "Requires PACKAGE_USAGE_STATS permission on device"),
            Capability("battery", True, "Battery level reported by companion"),
            Capability("network", True, "Network type reported by companion"),
            Capability("location", True, "Only if user grants location permission to companion"),
            Capability("permission_changes", False, "Android does not expose global permission-change audit to third parties"),
        ]

    async def sync(self):
        # Android data arrives via push endpoints; sync just refreshes device status
        if self.integration:
            self.integration.last_sync_at = datetime.now(timezone.utc)
            self.integration.status = "ok"
            if self.db: self.db.commit()
        return {"ok": True, "events_created": 0, "note": "Android companion pushes events; no pull sync."}
