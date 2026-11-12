from pydantic import BaseModel
from typing import Any


class EventIn(BaseModel):
    timestamp: str | None = None
    source: str
    account_id: str | None = None
    device_id: str | None = None
    integration_kind: str | None = None
    application: str | None = None
    event_type: str
    category: str | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None
    collection_method: str = "api"
    permission_status: str = "authorized"
    confidence: float = 1.0
    dedup_key: str | None = None
    raw: dict[str, Any] | None = None


from typing import Any as _Any

class EventOut(BaseModel):
    id: str
    user_id: str
    device_id: str | None = None
    account_id: str | None = None
    integration_kind: str | None = None
    source: str
    timestamp: _Any = None
    application: str | None = None
    event_type: str
    category: str | None = None
    description: str | None = None
    metadata: _Any = None
    collection_method: str
    permission_status: str
    confidence: float
    dedup_key: str | None = None

    model_config = {"from_attributes": True}


class EventQuery(BaseModel):
    source: str | None = None
    application: str | None = None
    event_type: str | None = None
    category: str | None = None
    device_id: str | None = None
    account_id: str | None = None
    start: str | None = None
    end: str | None = None
    q: str | None = None
    limit: int = 100
    offset: int = 0
