"""records module + sleeve grading

Vinyl is graded twice, independently: the disc and the sleeve. Collectors
write it as a pair ("VG+/VG"), and they diverge often enough that a single
condition would misreport value in both directions — so `owned` gains a
second grade. Only records use it; every other module leaves it null.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-04

"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "record_attrs",
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("collection_item.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("artist", sa.String(200)),
        sa.Column("label", sa.String(120)),
        sa.Column("catalog_number", sa.String(60)),
        sa.Column("format", sa.String(40)),      # LP / 2xLP / 7" / 12" single
        sa.Column("speed", sa.String(10)),       # 33 / 45 / 78
        sa.Column("pressing", sa.String(100)),   # colour, picture disc, reissue
        sa.Column("release_year", sa.Integer()),
        sa.Column("country", sa.String(10)),
        sa.Column("barcode", sa.String(20)),
        sa.Column("track_count", sa.Integer()),
    )
    op.create_index("ix_record_attrs_artist", "record_attrs", ["artist"])
    op.create_index("ix_record_attrs_barcode", "record_attrs", ["barcode"])
    # sleeve grade, alongside the existing `condition` which becomes the media grade
    op.add_column("owned", sa.Column("sleeve_condition", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("owned", "sleeve_condition")
    op.drop_table("record_attrs")
