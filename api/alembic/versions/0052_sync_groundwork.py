"""Two columns a collection needs before it can be mirrored somewhere else.

`binder.uid` — a name for a binder that survives being loaded into another
account. A restore used to delete every binder and make new ones, so their
ids changed each time, and a public link to `/u/bo/binder/17` broke the
moment the collection was restored — or, once syncing exists, every night.
Matched on this instead, a binder is updated in place and keeps its id.
Existing rows get one here; new rows get one from the model.

`api_token.scope` — what a bearer token may do. Every token so far is the
whole account. A token that lives on a home server so it can push a
collection to a hosted account needs to be able to do exactly that and
nothing else, because a database on somebody's NAS is not a vault.

Revision ID: 0052
Revises: 0051
"""

import sqlalchemy as sa
from alembic import op

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("binder", sa.Column("uid", sa.String(36), nullable=True))
    # gen_random_uuid() is core Postgres from 13; the stack ships 16
    op.execute("UPDATE binder SET uid = gen_random_uuid()::text WHERE uid IS NULL")
    op.alter_column("binder", "uid", nullable=False)
    op.create_index("ix_binder_uid", "binder", ["uid"], unique=True)

    op.add_column(
        "api_token",
        sa.Column("scope", sa.String(12), nullable=False, server_default="full"),
    )


def downgrade() -> None:
    op.drop_column("api_token", "scope")
    op.drop_index("ix_binder_uid", table_name="binder")
    op.drop_column("binder", "uid")
