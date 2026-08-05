"""accent-insensitive search

430 cards in the offline dump carry a diacritic — Flabébé, Poké Ball, every
Pokémon Trainer card — and nobody types é on a phone keyboard. Postgres ILIKE
folds case but not accents, so "pokemon catcher" matched nothing.

unaccent is a contrib module shipped with the official postgres images, so this
is just enabling it. Creating an extension needs superuser, which the bootstrap
role in the postgres container is.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-05

"""
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")


def downgrade() -> None:
    # queries call unaccent(), so dropping this breaks search until the code
    # is rolled back too
    op.execute("DROP EXTENSION IF EXISTS unaccent")
