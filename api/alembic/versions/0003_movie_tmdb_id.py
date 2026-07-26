"""movie_attrs.tmdb_id — metadata link without uniqueness

Movies deliberately do NOT use the (source, external_id) dedupe that games use:
owning the same film on Blu-ray and again as a 4K steelbook is normal, so the
TMDB id lives here as a plain metadata pointer instead.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-26

"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("movie_attrs", sa.Column("tmdb_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("movie_attrs", "tmdb_id")
