"""add users.mfa_recovery_codes (single-use backup codes)

Revision ID: 0003_recovery_codes
Revises: 0002_sessions_cutoff
Create Date: 2026-11-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_recovery_codes"
down_revision = "0002_sessions_cutoff"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("mfa_recovery_codes", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("mfa_recovery_codes")