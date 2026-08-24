"""Eight bytes describing what each card looks like.

So a photograph can be matched against the catalogue without asking anybody
anything — see app/arthash.py. Null everywhere on arrival and filled in by
seed/hash_cards.py, which is a long run over somebody else's CDN and
therefore a thing you start on purpose rather than something a migration
does while the server is trying to come up.

Deliberately unindexed. Nothing looks this column up by value: the question
is always "which of these is nearest", which reads the column rather than
seeks on it, and a btree over a hash would only cost writes.

Revision ID: 0051
Revises: 0050
"""

import sqlalchemy as sa
from alembic import op

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("card_attrs", sa.Column("art_hash", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("card_attrs", "art_hash")
