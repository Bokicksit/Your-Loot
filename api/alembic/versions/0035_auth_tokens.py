"""Links you can email somebody: verify this address, reset this password.

Accounts have been invite-only, which is right for a house server — a
stranger who finds it should not be able to make themselves one. A public
service cannot work that way, and the two things it needs before it can let
anybody sign up are a way to prove an address is real and a way back in when
somebody forgets their password.

Both are the same shape: a secret held for a while and spent once. So they
share a table and differ by `kind`, rather than the expiry and single-use
logic being written twice and drifting.

Hashed, like api_token, for the same reason: a copy of this table must not be
a copy of everybody's password reset. The raw value only ever exists in the
email.

`email_verified_at` on users is nullable and stays null for every account
that predates this — nobody was ever asked. It must never be read as "cannot
sign in", only as "cannot be sent a reset".

Revision ID: 0035
Revises: 0034
"""

import sqlalchemy as sa
from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(), nullable=True))

    op.create_table(
        "auth_token",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    # for sweeping expired rows without reading the live ones
    op.create_index("ix_auth_token_expiry", "auth_token", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_auth_token_expiry", table_name="auth_token")
    op.drop_table("auth_token")
    op.drop_column("users", "email_verified_at")
