"""info-panel data: card set release year + movie overview

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-27

"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("card_attrs", sa.Column("set_year", sa.Integer(), nullable=True))
    op.add_column("movie_attrs", sa.Column("overview", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("movie_attrs", "overview")
    op.drop_column("card_attrs", "set_year")
