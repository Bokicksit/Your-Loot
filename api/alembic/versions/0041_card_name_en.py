"""The English species name on a card printed in another language.

A Japanese card is titled リザードン, because that is what is printed on it,
and the title should keep saying so — it is what the card is called, what a
Japanese seller lists it as, and what goes into a search for one.

But almost nobody using this reads Japanese, and a catalogue you can only
search by typing リザードン is a catalogue with 13,000 cards nobody can find.
The dex number is the bridge: the card says 6, the English catalogue says 6
is Charizard, and that is a fact worth writing down once at seed time rather
than working out on every keystroke over thirty thousand rows.

Null on English cards, where the title already is the English name, and null
on anything with no dex number — a Trainer or an Item is not a species and
has nothing to borrow.

Revision ID: 0041
Revises: 0040
"""

import sqlalchemy as sa
from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("card_attrs", sa.Column("name_en", sa.String(120), nullable=True))


def downgrade() -> None:
    op.drop_column("card_attrs", "name_en")
