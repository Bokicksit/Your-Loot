"""A pocket in a binder of your own can hold more than one copy of a card.

Up to three of the exact same card — the same printing — the way a real
binder pocket takes a small stack of duplicates. Each copy is still its own
copy, with its own condition and grade; the pocket is what they share.

Modelled as rows behind a row. The pocket is the slot that has always been
there, with a position; a stacked copy is a second slot row that points at it
through `parent_id` and has no position of its own, because its place is the
pocket's. Everything that orders, resizes or counts a binder looks only at
the rows with no parent, so a stack is one pocket everywhere it matters and
three cards only where you open it.

CASCADE, so removing the pocket removes what was stacked in it — the same as
lifting the whole stack out at once.

Revision ID: 0054
Revises: 0053
"""

import sqlalchemy as sa
from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "binder_slot",
        sa.Column(
            "parent_id",
            sa.Integer(),
            sa.ForeignKey("binder_slot.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_binder_slot_parent", "binder_slot", ["parent_id"])


def downgrade() -> None:
    op.drop_index("ix_binder_slot_parent", table_name="binder_slot")
    op.drop_column("binder_slot", "parent_id")
