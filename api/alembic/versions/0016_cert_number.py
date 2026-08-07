"""Certification number on an owned copy.

A slab's cert number belongs to the copy, not to the card: two people can own
the same Charizard and only one of them holds cert 128637040. It is also the
key back to PSA, so a graded copy can be re-checked or looked up later.

Revision ID: 0016
Revises: 0015
"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("owned", sa.Column("cert_number", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("owned", "cert_number")
