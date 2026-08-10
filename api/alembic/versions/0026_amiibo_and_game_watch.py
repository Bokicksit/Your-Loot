"""Two things that scan as hardware but had nowhere to be filed.

An amiibo and a Game & Watch both come up as hardware — they are objects you
own rather than games you play — but the platform list only had consoles, so
there was no shelf to put them on.

Neither is a console, which is the point. `platforms` is what hardware is
filed under, so that is where they go, and a figure that belongs to no system
is more honest under "amiibo" than under whichever console it happens to touch.

Inserted by name rather than by id: an install that already has these, however
they got there, should keep the rows its collection points at.

Revision ID: 0026
Revises: 0025
"""

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None

NEW = [
    ("amiibo", "amiibo"),          # Nintendo styles it lowercase, so it stays that way
    ("Game & Watch", "G&W"),
]


def upgrade() -> None:
    for name, abbr in NEW:
        op.execute(
            sa.text(
                "INSERT INTO platforms (name, abbreviation) SELECT :name, :abbr "
                "WHERE NOT EXISTS (SELECT 1 FROM platforms WHERE name = :name)"
            ).bindparams(name=name, abbr=abbr)
        )


def downgrade() -> None:
    # only if nothing is filed under them — removing a platform out from under
    # somebody's console would orphan the row that points at it
    for name, _ in NEW:
        op.execute(
            sa.text(
                "DELETE FROM platforms WHERE name = :name AND NOT EXISTS "
                "(SELECT 1 FROM game_attrs WHERE platform_id = platforms.id)"
            ).bindparams(name=name)
        )
