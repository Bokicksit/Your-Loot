"""Your photo of a thing, kept apart from the thing.

This is the privacy fix, not a convenience. The card detail's image picker
writes straight to `collection_item.image_url` — the shared catalogue row. So
a photo of your own Charizard, sitting on your own desk, becomes the picture
every other person on the server sees for that card. Same for `notes`.

Nothing leaks today because there is one user. It has to be fixed before there
are two, and the fix is that anything personal about a catalogue item lives in
a row keyed by who wrote it.

The backfill is exact rather than a guess: the app already distinguishes these
(`isCatalogArt` in the web client). A picture served from `/images/` is on this
server because the owner put it there — uploaded, photographed or fetched from
a link. Anything else is the catalogue's own art, hotlinked from wherever it
came from.

It copies rather than moves. Nothing reads this table until the code that
prefers an override over the catalogue lands, and a migration that emptied
`collection_item.image_url` before then would blank every customised item in
the meantime.

Revision ID: 0021
Revises: 0020
"""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "item_override",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("collection_item.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.execute(
        """
        INSERT INTO item_override (user_id, item_id, image_url, notes)
        SELECT 1,
               id,
               CASE WHEN image_url LIKE '/images/%' THEN image_url END,
               notes
        FROM collection_item
        WHERE image_url LIKE '/images/%' OR notes IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_table("item_override")
