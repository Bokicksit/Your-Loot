"""Whether a binder appears on the public profile.

Publishing the cards shelf publishes the shelf — the binders on it and the
box of loose cards beside them. That is the right default, and it is the
default here: a binder that existed before this column did was already being
shown, and a migration that quietly emptied somebody's profile would be a
worse surprise than the one it was avoiding.

What this adds is the ability to hold one back. A binder of things being
traded away, a binder somebody is keeping to themselves — the collection is
public, that shelf is not. The cards in it stay where they are: hidden means
the binder is not drawn and its pages cannot be fetched, not that its cards
fall out into the loose box, which would publish the very thing that was
just hidden.

Revision ID: 0044
Revises: 0043
"""

import sqlalchemy as sa
from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "binder",
        sa.Column("on_profile", sa.Boolean(), nullable=False, server_default="true"),
    )


def downgrade() -> None:
    op.drop_column("binder", "on_profile")
