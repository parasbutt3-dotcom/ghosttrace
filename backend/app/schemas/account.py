from typing import Any

from pydantic import BaseModel


class AccountOut(BaseModel):
    id: str
    provider: str
    provider_account_id: str | None = None
    display_name: str | None = None
    email: str | None = None
    scopes: Any = None
    status: str
    token_expires_at: Any = None
    metadata: Any = None
    created_at: Any = None

    model_config = {"from_attributes": True}


class IntegrationOut(BaseModel):
    id: str
    kind: str
    name: str
    enabled: bool
    status: str
    last_sync_at: Any = None
    last_error: str | None = None
    last_sync_summary: Any = None
    config: Any = None
    created_at: Any = None

    model_config = {"from_attributes": True}


class DeviceOut(BaseModel):
    id: str
    name: str
    device_type: str
    platform: str | None = None
    os_version: str | None = None
    app_version: str | None = None
    battery_level: float | None = None
    network_type: str | None = None
    last_seen_at: Any = None
    last_location: Any = None
    status: str
    created_at: Any = None

    model_config = {"from_attributes": True}
