"""Copies and wants belong to somebody.

The catalogue does not: a Charizard is the same card whoever holds it, and the
whole point of the shared `collection_item` table is that it gets better as
more people add to it. Ownership is the part that is personal, so `user_id`
goes here and nowhere near the 20,000 catalogue rows.

`wanted.item_id` was UNIQUE, which quietly meant that exactly one person in
the world could want any given card. That was invisible while there was one
person in the world. It becomes UNIQUE (user_id, item_id): one entry each, per
person, which is what it always meant.

Both columns default to 1 in the database. That is what lets this migration
run against a live install without a matching code change — every existing
INSERT omits `user_id` and keeps working, landing on the owner. The default
comes off when sessions start supplying it explicitly.

Revision ID: 0019
Revises: 0018
"""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def _add_owner(table: str) -> None:
    op.add_column(
        table,
        sa.Column("user_id", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.create_foreign_key(
        f"fk_{table}_user", table, "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index(f"ix_{table}_user_id", table, ["user_id"])


def upgrade() -> None:
    _add_owner("owned")
    _add_owner("wanted")

    op.drop_constraint("wanted_item_id_key", "wanted", type_="unique")
    op.create_unique_constraint("uq_wanted_user_item", "wanted", ["user_id", "item_id"])


def downgrade() -> None:
    # Only safe while one person owns everything — with two users this drops
    # one of them and then collides on the old single-owner constraint.
    op.drop_constraint("uq_wanted_user_item", "wanted", type_="unique")
    op.execute("DELETE FROM wanted a USING wanted b WHERE a.item_id = b.item_id AND a.id > b.id")
    op.create_unique_constraint("wanted_item_id_key", "wanted", ["item_id"])

    for table in ("owned", "wanted"):
        op.drop_index(f"ix_{table}_user_id", table_name=table)
        op.drop_constraint(f"fk_{table}_user", table, type_="foreignkey")
        op.drop_column(table, "user_id")
