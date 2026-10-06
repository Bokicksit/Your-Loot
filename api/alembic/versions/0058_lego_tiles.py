"""LEGO Smart Tags somebody has paired with a Pokémon.

The LEGO Pokédex: each LEGO Pokémon set comes with a Smart Tag per Pokémon,
and tapping one with a phone captures it. A browser can read the tag's serial
but not the Pokémon written in its memory, so the first tap asks and this
table remembers.

Revision ID: 0058
Revises: 0057
"""

import sqlalchemy as sa
from alembic import op

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lego_tile",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("serial", sa.String(32), nullable=False),
        sa.Column("dex_no", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "serial", name="uq_lego_tile_user_serial"),
    )
    op.create_index("ix_lego_tile_user_id", "lego_tile", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_lego_tile_user_id", table_name="lego_tile")
    op.drop_table("lego_tile")
