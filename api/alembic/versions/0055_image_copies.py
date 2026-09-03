"""A kept copy of each linked picture, for when the link breaks.

See app/copies.py. One row per item; the file lives under IMAGE_DIR beside
the uploaded photographs, named by its content.

Revision ID: 0055
Revises: 0054
"""

import sqlalchemy as sa
from alembic import op

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_copy",
        sa.Column("item_id", sa.Integer(),
                  sa.ForeignKey("collection_item.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("name", sa.String(120), nullable=True),
        sa.Column("bytes", sa.Integer(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.Column("failed_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("image_copy")
