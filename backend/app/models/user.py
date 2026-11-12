import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret_enc: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Single-use recovery codes: list of {"hash": sha256 hex, "used": bool}
    mfa_recovery_codes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Email verification state.
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Verification token (stored in several alias columns for compatibility).
    email_verification_token: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    email_verify_token: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    verify_email_token: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    verification_token: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    # Optional webhook URL for alert delivery (httpx POST).
    webhook_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Tokens issued before this instant are dead (used by logout-all).
    sessions_invalid_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Compatibility aliases for email_verified.
    @property
    def is_verified(self):
        return self.email_verified

    @is_verified.setter
    def is_verified(self, v):
        self.email_verified = bool(v)

    @property
    def is_email_verified(self):
        return self.email_verified

    @is_email_verified.setter
    def is_email_verified(self, v):
        self.email_verified = bool(v)

    accounts: Mapped[list["ConnectedAccount"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # type: ignore[name-defined]
    integrations: Mapped[list["Integration"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # type: ignore[name-defined]
    devices: Mapped[list["Device"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # type: ignore[name-defined]
    events: Mapped[list["Event"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # type: ignore[name-defined]
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # type: ignore[name-defined]
    oauth_states: Mapped[list["OAuthState"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # type: ignore[name-defined]
    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # type: ignore[name-defined]
    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # type: ignore[name-defined]
