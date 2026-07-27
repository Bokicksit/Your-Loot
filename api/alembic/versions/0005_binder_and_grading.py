"""binder layers, set totals, grading, dex happy flags

- card_attrs.layer: 1 basic (incl. regular ex) / 2 full-art / 3 IR-SIR,
  classified from rarity at seed time
- card_attrs.set_total: printed set size ("91/108" -> 108) for search
- owned.grader/grade: card grading ("PSA" + "9")
- dex_slots: per-dex "happy with current card" flag for the binder view

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-26

"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "card_attrs",
        sa.Column("layer", sa.SmallInteger(), nullable=False, server_default="1"),
    )
    op.add_column("card_attrs", sa.Column("set_total", sa.Integer(), nullable=True))
    op.create_index("ix_card_attrs_card_number", "card_attrs", ["card_number"])
    op.add_column("owned", sa.Column("grader", sa.String(10), nullable=True))
    op.add_column("owned", sa.Column("grade", sa.String(6), nullable=True))
    op.create_table(
        "dex_slots",
        sa.Column("dex_no", sa.Integer(), primary_key=True),
        sa.Column("happy", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table("dex_slots")
    op.drop_column("owned", "grade")
    op.drop_column("owned", "grader")
    op.drop_index("ix_card_attrs_card_number", "card_attrs")
    op.drop_column("card_attrs", "set_total")
    op.drop_column("card_attrs", "layer")
