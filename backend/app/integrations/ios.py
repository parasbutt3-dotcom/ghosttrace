from app.integrations.base import BaseIntegration, Capability
from app.integrations.registry import register
from datetime import datetime, timezone


@register("ios")
class IOSIntegration(BaseIntegration):
    kind = "ios"
    display_name = "iOS Companion"

    def capabilities(self):
        return [
            Capability("device_registration", True, "Devices register with a device key"),
            Capability("screen_time", True, "Via Screen Time API (Family Controls) with user consent"),
            Capability("location", True, "Only if user grants location permission"),
            Capability("motion_activity", True, "CoreMotion activity data with user consent"),
            Capability("health_data", False, "HealthKit data requires explicit per-type authorization and is not auto-collected", requires=["HealthKit entitlements"]),
            Capability("background_refresh", True, "BGTaskScheduler with user permission"),
        ]

    async def sync(self):
        if self.integration:
            self.integration.last_sync_at = datetime.now(timezone.utc)
            self.integration.status = "ok"
            if self.db: self.db.commit()
        return {"ok": True, "events_created": 0, "note": "iOS companion pushes events; no pull sync."}
