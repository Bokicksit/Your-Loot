"""Which language a card was printed in.

Until now every card in the catalogue was English, so the language was not
worth writing down — a column that says the same thing on every row answers
nothing. Japanese sets change that: SV1a is a set that never existed in
English, and トロピウス and Tropius are different pieces of cardboard that a
collector keeps apart, prices apart and files in different binders.

Identity does not need this. `UNIQUE(source, external_id)` already keeps the
two catalogues from colliding, because the Japanese seed writes a different
source. What needs it is every question the app asks *about* a card:
"English only", "how many Japanese do I have", "which of these two Charizards
is the Japanese one". Those are filters, and a filter over a source string
would be reading identity as if it were a fact about the card.

Not null with a default, so every card already in the catalogue is English —
which is true, and means nothing has to be backfilled.

Revision ID: 0040
Revises: 0039
"""

import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "card_attrs",
        sa.Column(
            "language", sa.String(5), nullable=False, server_default="en"
        ),
    )
    # Indexed because "English only" is a filter on a list of thousands, and
    # the answer is almost all of them — which is exactly the shape a scan
    # handles badly once the Japanese half arrives.
    op.create_index("ix_card_attrs_language", "card_attrs", ["language"])


def downgrade() -> None:
    op.drop_index("ix_card_attrs_language", table_name="card_attrs")
    op.drop_column("card_attrs", "language")
