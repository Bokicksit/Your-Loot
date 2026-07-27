"""owned.in_binder — binder membership is per physical copy, opt-in

Only copies flagged in_binder occupy Pokédex binder slots; other copies
(box, slabs) stay collection-only.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-26

"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "owned",
        sa.Column("in_binder", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("owned", "in_binder")
