"""amiibo becomes its own collection.

They were only ever addable as hand-typed hardware, which is the wrong shelf:
an amiibo is a catalogued product line — 932 of them, each with an identity
Nintendo burned into the figure itself — not a console variant. A ninth
module, seeded from the open amiibo database the way cards are seeded, so
adding one is picking it rather than typing it.

The id column holds the head+tail hex pair an NFC reader sees, which is the
stable identity a personal restore matches on across installs.

Revision ID: 0048
Revises: 0047
"""

import sqlalchemy as sa
from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "amiibo_attrs",
        sa.Column(
            "item_id", sa.Integer(),
            sa.ForeignKey("collection_item.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("amiibo_id", sa.String(length=20), nullable=True),
        sa.Column("character", sa.String(length=80), nullable=True),
        sa.Column("amiibo_series", sa.String(length=80), nullable=True),
        sa.Column("game_series", sa.String(length=80), nullable=True),
        sa.Column("figure_type", sa.String(length=20), nullable=True),
        sa.Column("release_year", sa.Integer(), nullable=True),
        sa.Column("release_na", sa.String(length=10), nullable=True),
    )
    op.create_index("ix_amiibo_attrs_amiibo_id", "amiibo_attrs", ["amiibo_id"])
    op.create_index("ix_amiibo_attrs_character", "amiibo_attrs", ["character"])
    op.create_index("ix_amiibo_attrs_amiibo_series", "amiibo_attrs", ["amiibo_series"])
    op.create_index("ix_amiibo_attrs_figure_type", "amiibo_attrs", ["figure_type"])


def downgrade() -> None:
    op.drop_index("ix_amiibo_attrs_figure_type", table_name="amiibo_attrs")
    op.drop_index("ix_amiibo_attrs_amiibo_series", table_name="amiibo_attrs")
    op.drop_index("ix_amiibo_attrs_character", table_name="amiibo_attrs")
    op.drop_index("ix_amiibo_attrs_amiibo_id", table_name="amiibo_attrs")
    op.drop_table("amiibo_attrs")
