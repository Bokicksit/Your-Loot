"""Catalogue rows that belong to one person.

The catalogue is common ground — a Charizard is the same card whoever holds
it — and that is what makes it worth sharing. It works because the rows come
from somewhere everybody agrees on: a set list, a games database, a barcode.

An imported collection breaks that assumption. Anything somebody typed in by
hand has no external id, so an import has nothing to match it against and
must create a row; and it creates them in bulk. On a server with other people
on it, one person's "Dad's old NES, boxed" would arrive in everybody's search
results as though it were a fact about the world.

So a row can name the person it belongs to. It behaves exactly as any other
catalogue row does for them — their copies, their binders, their searches —
and does not exist for anybody else. Null, which is what every row has and
almost every row will keep, means shared as before.

Revision ID: 0046
Revises: 0045
"""

import sqlalchemy as sa
from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "collection_item",
        sa.Column("private_to", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_item_private_to", "collection_item", "users",
        ["private_to"], ["id"], ondelete="CASCADE",
    )
    # Every catalogue query filters on this, and all but a handful of rows
    # are null — a partial index keeps it small and still answers them.
    op.create_index(
        "ix_item_private_to", "collection_item", ["private_to"],
        postgresql_where=sa.text("private_to IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_item_private_to", table_name="collection_item")
    op.drop_constraint("fk_item_private_to", "collection_item", type_="foreignkey")
    op.drop_column("collection_item", "private_to")
