"""Tracklist on a record.

MusicBrainz gives a track *count* and nothing else, which tells you a record
has eleven sides of something. Discogs knows what they are, per pressing —
which matters, because the running order and the edits differ between a 1977
first press and a reissue, and that is the whole reason vinyl is tracked by
pressing here in the first place.

Stored as text, one track to a line, rather than a related table: nothing
queries it, sorts by it or joins to it. It is read back exactly as it was
written, and a column costs nothing.

Revision ID: 0017
Revises: 0016
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("record_attrs", sa.Column("tracklist", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("record_attrs", "tracklist")
