"""When somebody agreed to the terms.

A tick box that only the browser checks is decoration — it proves nothing
afterwards and can be skipped by anybody who opens the network tab. So the
server refuses a signup without it and writes down when it happened, which
is the only part that is any use later.

Null on every account that predates this and on every self-hosted install,
where there is no operator to have terms with. It must never be read as "has
not agreed" for those — only as "was never asked".

Revision ID: 0038
Revises: 0037
"""

import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("terms_accepted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "terms_accepted_at")
