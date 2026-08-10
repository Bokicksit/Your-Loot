"""Words you file things under.

A tag belongs to a person and to one collection. Both facts are in the table
rather than enforced by callers: `user_id` means a query that forgets to scope
returns nothing rather than everything, and `scope` means the records filter
bar offers hip-hop without also offering the labels from the LEGO shelf.

`scope` holds the collection as the app shows it, which is not quite the
module as the database stores it — hardware sits in the games table behind a
flag but is its own tab, so it gets 'hardware' and its own labels.

UNIQUE(user_id, scope, key) on the folded name is what stops hip-hop, Hip Hop
and HIP-HOP becoming three tags holding a third of the collection each.

Revision ID: 0024
Revises: 0023
"""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tag",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column("key", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "scope", "key", name="uq_tag_user_scope_key"),
    )
    op.create_index("ix_tag_user_id", "tag", ["user_id"])
    op.create_index("ix_tag_scope", "tag", ["scope"])

    op.create_table(
        "item_tag",
        sa.Column(
            "tag_id",
            sa.Integer(),
            sa.ForeignKey("tag.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("collection_item.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    # the direction the list endpoints read it: given these items, what tags?
    op.create_index("ix_item_tag_item", "item_tag", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_item_tag_item", table_name="item_tag")
    op.drop_table("item_tag")
    op.drop_index("ix_tag_scope", table_name="tag")
    op.drop_index("ix_tag_user_id", table_name="tag")
    op.drop_table("tag")
