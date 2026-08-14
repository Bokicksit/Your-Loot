"""Which printings a card exists in.

A master set is one slot per *printing*, not per card: the common Exeggcute in
Prismatic Evolutions was printed plain and reverse-holo, and a collector after
the master set needs both. Nothing in the offline dump says which printings a
card had — `card_attrs.variant` describes what a single row *is*, not what
else exists — so this is fetched from TCGdex the first time somebody makes a
master binder of that set, and kept.

Three nullable flags rather than one blob, because the question asked of them
is always "does a reverse of this exist". Null means nobody has asked yet,
which is different from false and has to stay different: a set nobody has
opened a master binder for should not claim every card is plain-only.

Revision ID: 0030
Revises: 0029
"""

import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for col in ("has_normal", "has_reverse", "has_holo"):
        op.add_column("card_attrs", sa.Column(col, sa.Boolean()))
    # so a set can be asked once rather than once per card that happens to be
    # missing an answer
    op.create_index(
        "ix_card_attrs_set_printings", "card_attrs", ["set_code", "has_normal"]
    )


def downgrade() -> None:
    op.drop_index("ix_card_attrs_set_printings", table_name="card_attrs")
    for col in ("has_holo", "has_reverse", "has_normal"):
        op.drop_column("card_attrs", col)
