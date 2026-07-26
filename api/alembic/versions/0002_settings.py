"""app settings key/value store (owner name, future prefs)

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-26

"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("key", sa.String(50), primary_key=True),
        sa.Column("value", sa.Text()),
    )


def downgrade() -> None:
    op.drop_table("settings")
