"""lego module

Set number is the identity — "10276-1" is the Colosseum, and the "-1" suffix
is Rebrickable's variant marker, kept because that's how their API returns it
and how a set is looked up again later.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-05

"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lego_attrs",
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("collection_item.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("set_number", sa.String(20)),
        sa.Column("theme", sa.String(80)),
        sa.Column("subtheme", sa.String(80)),
        sa.Column("release_year", sa.Integer()),
        sa.Column("piece_count", sa.Integer()),
        sa.Column("minifig_count", sa.Integer()),
        sa.Column("barcode", sa.String(20)),
    )
    op.create_index("ix_lego_attrs_set_number", "lego_attrs", ["set_number"])
    op.create_index("ix_lego_attrs_theme", "lego_attrs", ["theme"])
    op.create_index("ix_lego_attrs_barcode", "lego_attrs", ["barcode"])


def downgrade() -> None:
    op.drop_table("lego_attrs")
