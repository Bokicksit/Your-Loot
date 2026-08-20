"""Hardware learns what kind of thing it is.

Console, controller, or accessory — the question every manual hardware entry
starts with, previously answered nowhere, which made the add form feel like
a blank page. A fixed vocabulary rather than free text, so the filter stays
three choices instead of a folksonomy of "gamepad"/"pad"/"joystick".

Null on everything that exists, deliberately: guessing kinds from titles and
writing the guesses into data is how databases rot. Existing rows read as
unsorted and get set by their owners in two clicks.

Revision ID: 0049
Revises: 0048
"""

import sqlalchemy as sa
from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "game_attrs",
        sa.Column("hardware_kind", sa.String(length=20), nullable=True),
    )
    op.create_index("ix_game_attrs_hardware_kind", "game_attrs", ["hardware_kind"])


def downgrade() -> None:
    op.drop_index("ix_game_attrs_hardware_kind", table_name="game_attrs")
    op.drop_column("game_attrs", "hardware_kind")
