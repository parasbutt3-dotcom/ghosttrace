import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    integration_id: Mapped[str | None] = mapped_column(ForeignKey("integrations.id", ondelete="SET NULL"), nullable=True)
    device_key_hash: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)  # for android companion auth
    name: Mapped[str] = mapped_column(String(128))
    device_type: Mapped[str] = mapped_column(String(64), default="android")  # android, browser, desktop, ...
    platform: Mapped[str | None] = mapped_column(String(64), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    battery_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    network_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_location: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship(back_populates="devices")  # type: ignore[name-defined]
    integration: Mapped["Integration | None"] = relationship(back_populates="devices")  # type: ignore[name-defined]
    events: Mapped[list["Event"]] = relationship(back_populates="device", cascade="all, delete-orphan")  # type: ignore[name-defined]
