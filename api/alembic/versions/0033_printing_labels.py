"""What to call a printing, stored beside it.

The label was worked out from the code — `r-pb` meant "Premium parallel — Poké
Ball" — which works only for the foils and stamps that existed when the code
was written. The next set will invent one, and a name derived from a lookup
would come back as the code itself.

So the name is written down when the printing is learned, composed from the
parts TCGdex gave. A foil nobody has seen before gets its own slot and its own
name without anyone editing this app.

Revision ID: 0033
Revises: 0032
"""

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("card_printing", sa.Column("label", sa.String(80)))
    op.add_column("card_printing", sa.Column("short", sa.String(24)))
    # what a card was printed at — jumbo is a different collectible, and this
    # was only ever in the code before
    op.add_column("card_printing", sa.Column("size", sa.String(20)))


def downgrade() -> None:
    for col in ("size", "short", "label"):
        op.drop_column("card_printing", col)
