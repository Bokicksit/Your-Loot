"""Bearer tokens, for clients that cannot hold a cookie.

The web UI keeps its session cookie. This is for everything that is not a
browser on the same origin — a phone app most of all, where the session cookie
becomes a third-party cookie and is refused.

Only the hash is stored. A copy of this table is not a copy of everyone's
access, and a lost token cannot be read back out of it — it is shown once and
then only ever compared against.

Revision ID: 0027
Revises: 0026
"""

import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_token",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("prefix", sa.String(12), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_api_token_user_id", "api_token", ["user_id"])
    # every authenticated request looks a token up by this
    op.create_index("ix_api_token_hash", "api_token", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_api_token_hash", table_name="api_token")
    op.drop_index("ix_api_token_user_id", table_name="api_token")
    op.drop_table("api_token")
