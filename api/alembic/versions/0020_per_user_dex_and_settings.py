"""A binder each, and preferences each.

Both of these tables were keyed on the thing itself — `dex_slots` on the
national dex number, `settings` on the preference name. With one person that
reads as "slot 25" and "card_cols". With two it reads as "the only slot 25
there will ever be", so the second person to mark Pikachu happy would overwrite
the first, and one person choosing four cards across would change it for
everybody.

The key becomes the pair. A binder belongs to whoever filled it, and a
preference to whoever set it.

`settings` is the one to be careful with: it holds `owner_name` and the
enabled-module list, which are answers to "how do I want this to look" rather
than anything about the server. Per user is right for all of them.

Revision ID: 0020
Revises: 0019
"""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

# table -> the column it used to be keyed on
TABLES = {"dex_slots": "dex_no", "settings": "key"}


def upgrade() -> None:
    for table, col in TABLES.items():
        op.add_column(
            table,
            sa.Column("user_id", sa.Integer(), nullable=False, server_default=sa.text("1")),
        )
        op.drop_constraint(f"{table}_pkey", table, type_="primary")
        op.create_primary_key(f"{table}_pkey", table, ["user_id", col])
        op.create_foreign_key(
            f"fk_{table}_user", table, "users", ["user_id"], ["id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    for table, col in TABLES.items():
        # keep the owner's rows; anyone else's have nowhere to go under a
        # single-owner key
        op.execute(f"DELETE FROM {table} WHERE user_id <> 1")
        op.drop_constraint(f"fk_{table}_user", table, type_="foreignkey")
        op.drop_constraint(f"{table}_pkey", table, type_="primary")
        op.create_primary_key(f"{table}_pkey", table, [col])
        op.drop_column(table, "user_id")
