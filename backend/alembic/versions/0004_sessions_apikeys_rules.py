"""add user_sessions, api_keys, detection_rules tables

Revision ID: 0004_access_rules
Revises: 0003_recovery_codes
Create Date: 2026-11-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_access_rules"
down_revision = "0003_recovery_codes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("jti", sa.String(64), unique=True, index=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("revoked", sa.Boolean, default=False),
    )
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("name", sa.String(255)),
        sa.Column("key_hash", sa.String(64), unique=True, index=True),
        sa.Column("prefix", sa.String(12)),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "detection_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("name", sa.String(255)),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("event_type", sa.String(128), nullable=True),
        sa.Column("source", sa.String(128), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("application", sa.String(255), nullable=True),
        sa.Column("window_hours", sa.Integer, default=24),
        sa.Column("min_count", sa.Integer, default=1),
        sa.Column("severity", sa.String(16), default="medium"),
        sa.Column("enabled", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    op.drop_table("detection_rules")
    op.drop_table("api_keys")
    op.drop_table("user_sessions")