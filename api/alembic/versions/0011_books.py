"""books module

Fifth collection type — proves the shape: one attrs table keyed to
collection_item, everything else (owned/wanted copies, condition, photos,
the cross-module wanted list) comes from the shared machinery.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-04

"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "book_attrs",
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("collection_item.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("author", sa.String(200)),
        sa.Column("publisher", sa.String(120)),
        sa.Column("isbn", sa.String(20)),
        sa.Column("format", sa.String(30)),      # Hardcover / Paperback / ...
        sa.Column("edition", sa.String(100)),    # "First edition", "Folio Society"
        sa.Column("publish_year", sa.Integer()),
        sa.Column("page_count", sa.Integer()),
        sa.Column("series", sa.String(150)),
        sa.Column("blurb", sa.Text()),
    )
    op.create_index("ix_book_attrs_isbn", "book_attrs", ["isbn"])
    op.create_index("ix_book_attrs_author", "book_attrs", ["author"])


def downgrade() -> None:
    op.drop_table("book_attrs")
