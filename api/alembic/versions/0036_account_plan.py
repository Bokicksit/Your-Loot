"""Which plan an account is on, and until when.

Only the hosted service charges for anything. On every self-hosted install
these two columns sit at their defaults and nothing reads them, because
PAID_MODULES is empty there and no collection costs anything.

`plan_until` null on a supporter means it does not expire — which is what a
plan granted by hand means, and what a lifetime one would mean later. A plan
that does run out closes a door; it never deletes a row. Somebody who stops
paying still has every record they entered, and still has the backup button,
because leaving with your own collection is not a paid feature.

Revision ID: 0036
Revises: 0035
"""

import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("plan", sa.String(20), nullable=False, server_default="free"),
    )
    op.add_column("users", sa.Column("plan_until", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "plan_until")
    op.drop_column("users", "plan")
