"""A users table, and one row in it.

Nothing signs in yet. This exists so the columns that follow have something to
point at, and so the person already using this install becomes user 1 rather
than being invented later by a script that has to guess what was theirs.

Everything in the database today belongs to them, because they are the only
person who has ever touched it. That is a fact worth recording while it is
still true — after a second user exists, no migration can work out who owned
what.

Credentials are nullable on purpose. Single-user installs never set one: the
app signs itself in as this row and the login screen never appears. A password
gets filled in on the day the owner decides to invite somebody.

Revision ID: 0018
Revises: 0017
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=True),
        sa.Column("display_name", sa.String(50), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # The owner already told us their name at first run; reuse it rather than
    # asking again. No row and no name both land as NULL, which is fine.
    op.execute(
        """
        INSERT INTO users (id, display_name, is_admin)
        VALUES (1, (SELECT value FROM settings WHERE key = 'owner_name'), true)
        """
    )
    # the sequence still thinks it is about to hand out 1
    op.execute("SELECT setval(pg_get_serial_sequence('users', 'id'), 1, true)")


def downgrade() -> None:
    op.drop_table("users")
