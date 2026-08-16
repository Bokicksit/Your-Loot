"""Whose account this is at Stripe.

Kept so that a webhook arriving months later — a renewal, a failed card, a
cancellation — can be matched to a person without asking Stripe who they are
on every event.

Null everywhere until somebody actually subscribes, and null forever on every
self-hosted install, where billing does not exist at all.

Revision ID: 0037
Revises: 0036
"""

import sqlalchemy as sa
from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("stripe_customer_id", sa.String(64), nullable=True))
    op.create_index("ix_users_stripe_customer_id", "users", ["stripe_customer_id"])


def downgrade() -> None:
    op.drop_index("ix_users_stripe_customer_id", table_name="users")
    op.drop_column("users", "stripe_customer_id")
