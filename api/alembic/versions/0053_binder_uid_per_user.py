"""A binder's uid is unique per account, not per server.

0052 made it unique across the whole table, which is right for one person
restoring their own file and wrong the moment a collection is sent to two
accounts on the same server — or two people load the same shared file. The
uid travels with the binder, so both copies carry the same one, and the
second load hit the index. What the uid has to be is "this person's binder
that the file means", and that is unique within the account.

Revision ID: 0053
Revises: 0052
"""

from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_binder_uid", table_name="binder")
    op.create_unique_constraint("uq_binder_user_uid", "binder", ["user_id", "uid"])


def downgrade() -> None:
    op.drop_constraint("uq_binder_user_uid", "binder", type_="unique")
    op.create_index("ix_binder_uid", "binder", ["uid"], unique=True)
