"""Where a game lives on IGDB.

The partnership asks for user-facing attribution: a link back to the game on
IGDB.com beside the data they supplied. Their URLs are built from a slug —
"the-legend-of-zelda-breath-of-the-wild" — and the numeric id we already keep
does not produce one, so the link cannot be built from what is stored.

Kept beside the other game attributes rather than in the shared identity
columns, because it is not identity: `source` and `external_id` already say
which IGDB game this is and are what an import matches on. This is the
address of a page about it.

Null on every game added before this, and on everything hand-typed, which is
correct — a row that did not come from IGDB has nothing to credit them for.

Revision ID: 0047
Revises: 0046
"""

import sqlalchemy as sa
from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("game_attrs", sa.Column("igdb_slug", sa.String(length=160), nullable=True))


def downgrade() -> None:
    op.drop_column("game_attrs", "igdb_slug")
