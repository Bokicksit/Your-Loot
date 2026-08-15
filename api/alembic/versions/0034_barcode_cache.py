"""Remember what a barcode turned out to be.

Every scan asked UPCitemdb again, even for a barcode somebody else had
scanned an hour earlier. On one household that is merely wasteful; the free
tier is a hundred calls a day and a household never notices. Shared by many
people it is the whole problem — the same PS2 game scanned by a hundred
people was a hundred calls, and a hundred calls is the entire daily budget.

A barcode means one thing forever, so the answer is worth keeping. The first
person to scan Twilight Princess pays a call and everybody after reads this
table. The cost stops being "users times scans" and becomes "distinct
products anyone has ever scanned", which flattens out instead of growing.

Misses are kept too, and deliberately: a barcode the database does not know
is still an answer, and asking again tomorrow will not change it. It carries
a date so a miss can be retried eventually without retrying it constantly.

Revision ID: 0034
Revises: 0033
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "barcode_cache",
        sa.Column("code", sa.String(20), primary_key=True),
        # the provider's answer, as given — a list of products with their
        # titles and retailer photographs
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("found", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("fetched_at", sa.DateTime(), server_default=sa.func.now()),
    )
    # for pruning stale misses without scanning the hits
    op.create_index(
        "ix_barcode_cache_miss", "barcode_cache", ["found", "fetched_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_barcode_cache_miss", table_name="barcode_cache")
    op.drop_table("barcode_cache")
