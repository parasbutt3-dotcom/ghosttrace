import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Text, JSON, Float, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[str | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True)
    account_id: Mapped[str | None] = mapped_column(ForeignKey("connected_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    integration_kind: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(128), index=True)  # originating source name
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    application: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    collection_method: Mapped[str] = mapped_column(String(64))  # oauth_api, device_sdk, webhook, manual, ...
    permission_status: Mapped[str] = mapped_column(String(32), default="authorized")  # authorized, partial, unavailable
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    dedup_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship(back_populates="events")
    device: Mapped["Device | None"] = relationship(back_populates="events")


Index("ix_events_user_ts", Event.user_id, Event.timestamp)
Index("ix_events_dedup", Event.user_id, Event.dedup_key)
