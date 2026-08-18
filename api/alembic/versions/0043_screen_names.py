"""Screen names: claimed once, and never changed.

A public profile needs a name in a URL, and this application is not a social
network — so the name is chosen once and kept, the way it works on most sites
that predate the habit of letting people rename themselves. That decision
removes a great deal: no aliases, no redirects, no wondering which of
somebody's four old URLs is the real one.

It is a table rather than a column because a name has to outlive its owner
holding it. When an administrator takes an inappropriate name away, that name
must not become available again — not to the person who chose it, and not to
anybody else. So the row stays, marked revoked, and the unique index across
every row is what makes it permanent.

That is the whole difference between this and a rename: a rename would want
the old URL to keep working, and a revocation wants it gone.

Which collections a profile shows lives in `settings` beside `owner_name`,
because it is a preference about presentation and that is what that table is
for. Nothing is public until it is switched on.

Revision ID: 0043
Revises: 0042
"""

import sqlalchemy as sa
from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "screen_name",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        # folded to lower case: the URL is case-insensitive, so two people
        # cannot hold names that differ only in capitals
        sa.Column("name", sa.String(30), nullable=False),
        # as the owner typed it, for showing back to them
        sa.Column("display", sa.String(30), nullable=False),
        # Taken away by an administrator. The row stays so the name can never
        # be claimed again — by anybody, including whoever chose it.
        sa.Column(
            "revoked", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # Across every name ever held, revoked included. This index is the reason
    # a revocation is permanent.
    op.create_index("uq_screen_name", "screen_name", ["name"], unique=True)
    # One live name per account. A revoked row does not count, which is what
    # lets somebody claim a replacement after theirs was taken away.
    op.create_index(
        "uq_screen_name_live", "screen_name", ["user_id"],
        unique=True, postgresql_where=sa.text("NOT revoked"),
    )


def downgrade() -> None:
    op.drop_index("uq_screen_name_live", table_name="screen_name")
    op.drop_index("uq_screen_name", table_name="screen_name")
    op.drop_table("screen_name")
