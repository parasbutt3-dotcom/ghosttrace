"""alert acknowledgement state + webhook url + integration sync summary

Revision ID: 0003_alert_ack
Revises: 0002_email_verification
Create Date: 2026-11-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_alert_ack"
down_revision = "0002_email_verification"
branch_labels = None
depends_on = None


def upgrade():
    # user webhook url
    op.add_column("users", sa.Column("webhook_url", sa.String(512), nullable=True))
    # integration last sync summary (added by 3.6, ensure baseline has it)
    try:
        op.add_column("integrations", sa.Column("last_sync_summary", sa.JSON(), nullable=True))
    except Exception:
        pass
    op.create_table(
        "alert_acks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("fingerprint", sa.String(255), nullable=False, index=True),
        sa.Column("dismissed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint("uq_alert_ack_user_fingerprint", "alert_acks", ["user_id", "fingerprint"])


def downgrade():
    op.drop_constraint("uq_alert_ack_user_fingerprint", "alert_acks", type_="unique")
    op.drop_table("alert_acks")
    op.drop_column("integrations", "last_sync_summary")
    op.drop_column("users", "webhook_url")