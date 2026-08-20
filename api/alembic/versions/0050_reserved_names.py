"""Names an administrator has set aside.

A screen name is claimed once and never changed, which makes the moment of
claiming the only moment that matters — and an operator with a household
knows names that must survive until their people get around to signing up.
A reservation holds one: nobody may claim it, except the account whose email
the administrator wrote on it, whose claim consumes it.

Revision ID: 0050
Revises: 0049
"""

import sqlalchemy as sa
from alembic import op

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reserved_name",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=30), nullable=False, unique=True),
        sa.Column("display", sa.String(length=30), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("reserved_name")
