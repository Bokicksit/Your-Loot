"""movie_attrs.genre — primary genre from TMDB (or manual), for filtering

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-26

"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("movie_attrs", sa.Column("genre", sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column("movie_attrs", "genre")
