"""game_attrs metadata for the expandable info panel (from IGDB at add time)

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-26

"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("game_attrs", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("game_attrs", sa.Column("release_year", sa.Integer(), nullable=True))
    op.add_column("game_attrs", sa.Column("genres", sa.String(120), nullable=True))
    op.add_column("game_attrs", sa.Column("developer", sa.String(100), nullable=True))
    op.add_column("game_attrs", sa.Column("publisher", sa.String(100), nullable=True))


def downgrade() -> None:
    for col in ("publisher", "developer", "genres", "release_year", "summary"):
        op.drop_column("game_attrs", col)
