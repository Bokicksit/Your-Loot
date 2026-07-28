"""hardware tracking: model, serial, working status, accessory->console link

Hardware stays in the games module (is_hardware=true) but gets its own UI
tab and these per-unit fields. parent_id links an accessory to its console.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-27

"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("game_attrs", sa.Column("model_number", sa.String(50), nullable=True))
    op.add_column("game_attrs", sa.Column("serial_number", sa.String(60), nullable=True))
    op.add_column("game_attrs", sa.Column("working", sa.String(12), nullable=True))
    op.add_column(
        "game_attrs",
        sa.Column(
            "parent_id",
            sa.Integer(),
            sa.ForeignKey("collection_item.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("game_attrs", "parent_id")
    op.drop_column("game_attrs", "working")
    op.drop_column("game_attrs", "serial_number")
    op.drop_column("game_attrs", "model_number")
