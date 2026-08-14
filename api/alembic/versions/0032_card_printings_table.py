"""Every way a card was printed, one row each.

Three booleans could not carry this. `has_normal / has_reverse / has_holo`
folded the parallel set, the Poké Ball parallel and the Master Ball parallel
into a single "reverse", which cost Prismatic Evolutions 167 of its 476
printings — a master set that says you are finished when you are not.

The booklet that ships with the set is the model: a card has a row of boxes,
one per way it exists, and they are not the same boxes for every card.
Exeggcute has four, Briar has three, an ACE SPEC has one. So this is a table
rather than columns, because the number of them is a property of the card.

The names come from that booklet and from TCGdex's own fields, which agree:
  kind   normal | reverse | holo          — the print itself
  foil   pokeball | masterball | cosmos | gold | null
  stamp  set-logo | snowflake | 30th-pokeday | null

Revision ID: 0032
Revises: 0031
"""

import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "card_printing",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "item_id", sa.Integer(),
            sa.ForeignKey("collection_item.id", ondelete="CASCADE"), nullable=False,
        ),
        # our own short code for the whole combination — it is what a binder
        # slot stores, and slot keys have twenty characters to live in
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("foil", sa.String(20)),
        sa.Column("stamp", sa.String(30)),
        # the order the set lists them in, so the boxes read left to right the
        # way they are printed
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("item_id", "code", name="uq_card_printing"),
    )
    op.create_index("ix_card_printing_item", "card_printing", ["item_id"])

    # The three flags go. What they knew is a strict subset of what the table
    # holds, and keeping them would leave two answers to one question.
    #
    # The index first: it is built on has_normal, and Postgres drops it along
    # with the column, so asking for it afterwards is asking for something
    # that is already gone.
    op.drop_index("ix_card_attrs_set_printings", table_name="card_attrs")
    for col in ("has_normal", "has_reverse", "has_holo"):
        op.drop_column("card_attrs", col)


def downgrade() -> None:
    for col in ("has_normal", "has_reverse", "has_holo"):
        op.add_column("card_attrs", sa.Column(col, sa.Boolean()))
    op.create_index(
        "ix_card_attrs_set_printings", "card_attrs", ["set_code", "has_normal"]
    )
    # Fold the table back into the flags it replaced. Lossy on purpose — the
    # three parallels become one "reverse", which is exactly the limitation
    # this migration exists to remove.
    op.execute("""
        UPDATE card_attrs a SET
            has_normal  = EXISTS (SELECT 1 FROM card_printing p
                                  WHERE p.item_id = a.item_id AND p.kind = 'normal'),
            has_reverse = EXISTS (SELECT 1 FROM card_printing p
                                  WHERE p.item_id = a.item_id AND p.kind = 'reverse'),
            has_holo    = EXISTS (SELECT 1 FROM card_printing p
                                  WHERE p.item_id = a.item_id AND p.kind = 'holo')
        WHERE EXISTS (SELECT 1 FROM card_printing p WHERE p.item_id = a.item_id)
    """)
    op.drop_index("ix_card_printing_item", table_name="card_printing")
    op.drop_table("card_printing")
