"""Whether a binder takes Japanese cards.

Owning Japanese cards and wanting them in your Pokédex are different
decisions. A dex slot takes any card of that species, so the day a Japanese
Charizard enters the collection it is eligible for the Charizard slot — and
for somebody who buys the occasional Japanese card as a curiosity, that is
their English binder quietly rearranging itself.

So a binder says whether they belong in it, and the default is no. Not
because Japanese cards are lesser, but because the binder existed first and
was English when it did: a setting that changes what is already on the shelf
should have to be asked for.

Only the Pokédex and custom binders have the question at all. A set binder is
a set, and the Japanese sets are not offered as binders — there is no
"Triplet Beat, in English" for a slot to be ambiguous about.

Revision ID: 0042
Revises: 0041
"""

import sqlalchemy as sa
from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "binder",
        sa.Column("allow_ja", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("binder", "allow_ja")
