"""Accounts that are Supporters without being customers.

Friends, family, the people who tested it — somebody an operator wants to
give the paid tier to as a thank-you rather than as a sale. The plan is real
and works exactly as a bought one does; what changes is the arithmetic.

Because "subscribers" is a number you check to find out how the thing is
going, and one that counts the six people you comped is not that number. It
would read as revenue that does not exist, and every month it would be
wrong by the same amount in the same direction, which is the kind of wrong
you stop noticing.

Admins were already excluded from the count for the same reason. This is
the same exemption, said out loud, for people who are not admins.

Revision ID: 0045
Revises: 0044
"""

import sqlalchemy as sa
from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("comped", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("users", "comped")
