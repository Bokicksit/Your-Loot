"""A set binder can count only what is filed in it.

Owning a card used to fill its slot in every set binder: the shelf said you
had the card, wherever the copy actually was. That is the wrong answer for a
binder you are building — a Charizard in the Pokédex is not in the set
binder, and the set binder should say so until you put one there. So a set
binder now carries the rule it counts by: what is filed in it, like the
Pokédex, or anything in the collection, the way it always was.

Existing binders keep the old rule, so nothing on anybody's shelf empties out
on upgrade; the switch is theirs to flip.

Revision ID: 0057
Revises: 0056
"""

import sqlalchemy as sa
from alembic import op

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "binder",
        sa.Column(
            "whole_collection", sa.Boolean(), nullable=False, server_default="true"
        ),
    )


def downgrade() -> None:
    op.drop_column("binder", "whole_collection")
