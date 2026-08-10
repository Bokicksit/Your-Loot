"""Country names are longer than country codes.

`country` was sized at 10 for MusicBrainz, which answers in ISO codes — US,
GB, XE. The barcode scanner goes to Discogs instead, and Discogs answers with
the name written out: "USA & Europe" is 12, "Czech Republic" is 14, and plain
"Netherlands" and "Switzerland" are 11 apiece. Every one of those was refused,
which read as the scan failing rather than one field being two characters too
narrow.

`pressing` goes the same way for the same reason. It is a join of every format
descriptor Discogs lists for a release, and a well-documented reissue —
"Album, Limited Edition, Numbered, Reissue, Remastered, 180 Gram, Gatefold" —
runs past 100 before it has said anything unusual.

Nothing already stored is affected: widening a varchar rewrites no rows.

Revision ID: 0023
Revises: 0022
"""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "record_attrs", "country", type_=sa.String(60), existing_nullable=True
    )
    op.alter_column(
        "record_attrs", "pressing", type_=sa.String(200), existing_nullable=True
    )


def downgrade() -> None:
    # Narrowing is the direction that loses things, so say so rather than
    # letting Postgres refuse the whole migration over one long row.
    op.execute("UPDATE record_attrs SET country = left(country, 10) WHERE length(country) > 10")
    op.execute("UPDATE record_attrs SET pressing = left(pressing, 100) WHERE length(pressing) > 100")
    op.alter_column(
        "record_attrs", "country", type_=sa.String(10), existing_nullable=True
    )
    op.alter_column(
        "record_attrs", "pressing", type_=sa.String(100), existing_nullable=True
    )
