"""Where each binder sits on the shelf.

Kind and then name is a reasonable order and nobody's actual order. A real
shelf is arranged by what you reach for: the set you are working through at
eye level, the Pokédex next to it, the trades pile at the end.

Null means never placed, and those sort after the ones that have been, so
adding a binder puts it at the end rather than somewhere in the middle of an
arrangement you made.

Revision ID: 0031
Revises: 0030
"""

import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("binder", sa.Column("position", sa.Integer()))


def downgrade() -> None:
    op.drop_column("binder", "position")
