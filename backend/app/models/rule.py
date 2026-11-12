import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DetectionRule(Base):
    """User-defined detection rule: when >= min_count events match the filters
    within window_hours, the Security Center surfaces an alert."""
    __tablename__ = "detection_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    event_type: Mapped[str | None] = mapped_column(String(128), nullable=True)  # exact match
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)  # exact match
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)  # exact match
    application: Mapped[str | None] = mapped_column(String(255), nullable=True)  # exact match
    window_hours: Mapped[int] = mapped_column(Integer, default=24)  # 1..720
    min_count: Mapped[int] = mapped_column(Integer, default=1)  # threshold to fire
    severity: Mapped[str] = mapped_column(String(16), default="medium")  # info|low|medium|high
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship()  # type: ignore[name-defined]