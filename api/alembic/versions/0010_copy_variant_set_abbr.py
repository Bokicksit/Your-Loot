"""per-copy holo variant + stamp, and printed set abbreviations

- owned.variant: Non-Holo / Reverse Holo / Holo — a property of YOUR copy,
  the catalog entry is the same card
- owned.stamp: promo stamps ("Mega Evolution", "Prerelease", "Staff"…)
- card_attrs.set_abbr: the code printed on modern cards (MEW, JTG, SVI),
  from the dump's ptcgoCode — reseed backfills

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-27

"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("owned", sa.Column("variant", sa.String(20), nullable=True))
    op.add_column("owned", sa.Column("stamp", sa.String(60), nullable=True))
    op.add_column("card_attrs", sa.Column("set_abbr", sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column("card_attrs", "set_abbr")
    op.drop_column("owned", "stamp")
    op.drop_column("owned", "variant")
