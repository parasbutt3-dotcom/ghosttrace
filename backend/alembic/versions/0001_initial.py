"""initial schema (full baseline)

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=True),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False, default=False),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, default=False),
        sa.Column("mfa_secret_enc", sa.String(255), nullable=True),
        sa.Column("mfa_recovery_codes", sa.JSON(), nullable=True),
        sa.Column("sessions_invalid_before", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "connected_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("provider", sa.String(64), nullable=False, index=True),
        sa.Column("provider_account_id", sa.String(255), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("scopes", sa.JSON(), nullable=True),
        sa.Column("access_token_enc", sa.Text(), nullable=True),
        sa.Column("refresh_token_enc", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, default="connected"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "integrations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("connected_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(64), nullable=False, index=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, default=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, default="idle"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "devices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("integration_id", sa.String(36), sa.ForeignKey("integrations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("device_key_hash", sa.String(255), nullable=True, index=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("device_type", sa.String(64), nullable=False, default="android"),
        sa.Column("platform", sa.String(64), nullable=True),
        sa.Column("os_version", sa.String(64), nullable=True),
        sa.Column("app_version", sa.String(64), nullable=True),
        sa.Column("battery_level", sa.Float(), nullable=True),
        sa.Column("network_type", sa.String(32), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_location", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("device_id", sa.String(36), sa.ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("connected_accounts.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("integration_kind", sa.String(64), nullable=True, index=True),
        sa.Column("source", sa.String(128), nullable=False, index=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("application", sa.String(255), nullable=True, index=True),
        sa.Column("event_type", sa.String(128), nullable=False, index=True),
        sa.Column("category", sa.String(64), nullable=True, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("collection_method", sa.String(64), nullable=False),
        sa.Column("permission_status", sa.String(32), nullable=False, default="authorized"),
        sa.Column("confidence", sa.Float(), nullable=False, default=1.0),
        sa.Column("dedup_key", sa.String(255), nullable=True, index=True),
        sa.Column("raw", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_events_user_ts", "events", ["user_id", "timestamp"])
    op.create_index("ix_events_dedup", "events", ["user_id", "dedup_key"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("action", sa.String(128), nullable=False, index=True),
        sa.Column("resource", sa.String(128), nullable=True),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, default="success"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
    )

    op.create_table(
        "oauth_states",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("state", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("code_verifier", sa.Text(), nullable=True),
        sa.Column("redirect_uri", sa.Text(), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "revoked_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("jti", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("jti", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, default=False),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("prefix", sa.String(12), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "detection_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("event_type", sa.String(128), nullable=True),
        sa.Column("source", sa.String(128), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("application", sa.String(255), nullable=True),
        sa.Column("window_hours", sa.Integer(), nullable=False, default=24),
        sa.Column("min_count", sa.Integer(), nullable=False, default=1),
        sa.Column("severity", sa.String(16), nullable=False, default="medium"),
        sa.Column("enabled", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("detection_rules")
    op.drop_table("api_keys")
    op.drop_table("user_sessions")
    op.drop_table("revoked_tokens")
    op.drop_table("oauth_states")
    op.drop_table("audit_logs")
    op.drop_table("events")
    op.drop_table("devices")
    op.drop_table("integrations")
    op.drop_table("connected_accounts")
    op.drop_table("users")