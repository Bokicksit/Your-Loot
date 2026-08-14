"""A picture on the front of a binder.

A shelf of binders all called something and showing nothing is hard to read at
a glance, which is the one thing a shelf is for. This is the cover: a photo of
the real binder, or the art of the card the binder is about.

Nullable, and nothing fills it in — a binder without one draws its progress
bar as before.

Revision ID: 0029
Revises: 0028
"""

import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("binder", sa.Column("image_url", sa.String(500)))


def downgrade() -> None:
    op.drop_column("binder", "image_url")
