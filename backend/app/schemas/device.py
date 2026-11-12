from typing import Any

from pydantic import BaseModel, Field


class TelemetryEventIn(BaseModel):
    application: str | None = None
    event_type: str = Field(default="usage", max_length=128)
    timestamp: Any = None
    category: str | None = Field(default="activity", max_length=64)
    description: str | None = None
    metadata: dict[str, Any] | None = None
    collection_method: str = "device_sdk"
    permission_status: str = "authorized"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    dedup_key: str | None = None


class TelemetryIn(BaseModel):
    battery_level: float | None = Field(default=None, ge=0, le=100)
    network_type: str | None = Field(default=None, max_length=64)
    location: dict[str, Any] | None = None
    app_version: str | None = Field(default=None, max_length=64)
    os_version: str | None = Field(default=None, max_length=64)
    events: list[TelemetryEventIn] = Field(default_factory=list)