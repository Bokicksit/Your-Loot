"""What kind of record it is.

Discogs answers with a list — a record can be filed under Funk and Soul at
once — and this keeps the first, which is the one Discogs leads with and the
one a crate divider would say. A single value is what lets the filter be an
exact match like artist, label and format already are.

Existing rows stay empty until the backfill fills them in; a genre nobody has
is simply a filter option that doesn't appear.

Revision ID: 0025
Revises: 0024
"""

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("record_attrs", sa.Column("genre", sa.String(60), nullable=True))


def downgrade() -> None:
    op.drop_column("record_attrs", "genre")
