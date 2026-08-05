"""comics module

No new `owned` columns: a slabbed comic is graded exactly like a slabbed card,
so CGC/CBCS reuse the existing grader+grade pair, and a raw copy uses
`condition` on its own.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-05

"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "comic_attrs",
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("collection_item.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("series", sa.String(200)),
        sa.Column("issue_number", sa.String(20)),  # str: "1A", "0", "½"
        sa.Column("volume_year", sa.Integer()),    # which run: ASM (2018)
        sa.Column("publisher", sa.String(120)),
        sa.Column("cover_year", sa.Integer()),
        sa.Column("variant", sa.String(150)),      # "Campbell variant", 1:25
        sa.Column("creators", sa.String(300)),
        sa.Column("barcode", sa.String(20)),
        sa.Column("blurb", sa.Text()),
    )
    op.create_index("ix_comic_attrs_series", "comic_attrs", ["series"])
    op.create_index("ix_comic_attrs_barcode", "comic_attrs", ["barcode"])


def downgrade() -> None:
    op.drop_table("comic_attrs")
