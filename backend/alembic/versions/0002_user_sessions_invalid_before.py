"""add users.sessions_invalid_before (global sign-out cutoff)

Revision ID: 0002_sessions_cutoff
Revises: 0001_initial
Create Date: 2026-11-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_sessions_cutoff"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("sessions_invalid_before", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("sessions_invalid_before")
