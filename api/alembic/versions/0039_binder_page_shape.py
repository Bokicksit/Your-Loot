"""What shape the binder is.

Until now a binder was an ordered list of cards and the app chose how wide to
draw it, with a slider the reader moved. That is a fine way to draw a list and
a poor way to draw a binder, because a real one has a shape you did not
choose: nine pockets to a page, or twelve, and two pages facing you when it is
open on the table. Somebody looking for the card they know is top-left of the
fourth page is looking for a position, and a grid that reflows to taste does
not have positions.

So the shape moves onto the binder. None of it changes what is in the binder
or what order it is in — these four columns only decide where the page breaks
fall and what colour the edges are, which is why changing them later is safe
and cannot disturb a card.

Three of nine pockets is the default because it is the common page, and
because it is what every existing binder was already effectively being drawn
as at the middle of the old slider.

Revision ID: 0039
Revises: 0038
"""

import sqlalchemy as sa
from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "binder",
        sa.Column("rows", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "binder",
        sa.Column("cols", sa.Integer(), nullable=False, server_default="3"),
    )
    # A spread: two pages facing, the way the binder sits open.
    op.add_column(
        "binder",
        sa.Column(
            "double_page", sa.Boolean(), nullable=False, server_default="false"
        ),
    )
    # "#rrggbb", or null to keep the colour the shelf makes up from the kind
    # and the name. Short enough that anything longer is not a colour.
    op.add_column("binder", sa.Column("color", sa.String(7), nullable=True))


def downgrade() -> None:
    op.drop_column("binder", "color")
    op.drop_column("binder", "double_page")
    op.drop_column("binder", "cols")
    op.drop_column("binder", "rows")
