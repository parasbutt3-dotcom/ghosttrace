"""email verification columns on users

Revision ID: 0002_email_verification
Revises: 0001_initial
Create Date: 2026-11-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_email_verification"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("email_verification_token", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("email_verify_token", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("verify_email_token", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("verification_token", sa.String(255), nullable=True))
    op.create_index("ix_users_email_verification_token", "users", ["email_verification_token"])
    op.create_index("ix_users_email_verify_token", "users", ["email_verify_token"])
    op.create_index("ix_users_verify_email_token", "users", ["verify_email_token"])
    op.create_index("ix_users_verification_token", "users", ["verification_token"])


def downgrade():
    op.drop_index("ix_users_verification_token", table_name="users")
    op.drop_index("ix_users_verify_email_token", table_name="users")
    op.drop_index("ix_users_email_verify_token", table_name="users")
    op.drop_index("ix_users_email_verification_token", table_name="users")
    op.drop_column("users", "verification_token")
    op.drop_column("users", "verify_email_token")
    op.drop_column("users", "email_verify_token")
    op.drop_column("users", "email_verification_token")
    op.drop_column("users", "email_verified")