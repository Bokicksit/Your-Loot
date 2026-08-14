"""More than one binder.

Until now there was exactly one, and it was implied rather than stored: a copy
was in it if `owned.in_binder` was set, and `dex_slots` held the flag saying
you were happy with what was there. Neither can answer "which binder", so
neither survives a second one.

So: a `binder` row per binder, and a `binder_slot` row wherever there is
something to remember. The Pokédex becomes the first row rather than a special
case, and the two old structures are folded into it here.

The fold has to be exact, because there is no second chance at it — the flags
are the only record of which cards were in the binder. On the install this was
written against that is 881 filed copies, and 136 keeper flags out of 879
`dex_slots` rows (most of those rows say nothing: happy defaults to false). So
it moves the data first, counts what it moved, and refuses to drop anything if
the counts disagree.

Revision ID: 0028
Revises: 0027
"""

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "binder",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("set_code", sa.String(30)),
        sa.Column("master", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_binder_user_id", "binder", ["user_id"])
    # one Pokédex each, and one binder per set per mode
    op.create_index(
        "uq_binder_one_dex", "binder", ["user_id"],
        unique=True, postgresql_where=sa.text("kind = 'dex'"),
    )
    op.create_index(
        "uq_binder_one_set", "binder", ["user_id", "set_code", "master"],
        unique=True, postgresql_where=sa.text("kind = 'set'"),
    )

    op.create_table(
        "binder_slot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "binder_id", sa.Integer(),
            sa.ForeignKey("binder.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("slot_key", sa.String(20)),
        # never null: the unique index below relies on it, and Postgres
        # would let two nulls share a slot
        sa.Column("variant", sa.String(20), nullable=False, server_default=""),
        sa.Column("position", sa.Integer()),
        sa.Column(
            "item_id", sa.Integer(),
            sa.ForeignKey("collection_item.id", ondelete="CASCADE"),
        ),
        # SET NULL: the card leaving empties the slot rather than erasing it,
        # so the keeper flag survives a sale
        sa.Column(
            "owned_id", sa.Integer(), sa.ForeignKey("owned.id", ondelete="SET NULL")
        ),
        sa.Column("happy", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_binder_slot_binder_id", "binder_slot", ["binder_id"])
    op.create_index("ix_binder_slot_owned", "binder_slot", ["owned_id"])
    op.create_index(
        "uq_binder_slot_key", "binder_slot",
        ["binder_id", "slot_key", "variant"], unique=True,
    )

    conn = op.get_bind()

    # --- fold the one binder that already exists into the new shape ---------
    #
    # A binder for anyone who had either half of the old state. Somebody who
    # never opened the Pokédex gets nothing, and picks one up the first time
    # they file a card.
    conn.execute(sa.text("""
        INSERT INTO binder (user_id, name, kind)
        SELECT id, 'National Pokédex', 'dex' FROM users u
        WHERE EXISTS (SELECT 1 FROM dex_slots d WHERE d.user_id = u.id)
           OR EXISTS (SELECT 1 FROM owned o WHERE o.user_id = u.id AND o.in_binder)
    """))

    # Filed copies. The dex number comes from the card, which is why this
    # joins out to card_attrs rather than trusting the flag alone — a copy
    # flagged into the binder whose card has no dex number was never really
    # in it and has nowhere to go.
    filed = conn.execute(sa.text("""
        INSERT INTO binder_slot (binder_id, slot_key, owned_id)
        SELECT b.id, ca.national_dex_no::text, o.id
        FROM owned o
        JOIN collection_item ci ON ci.id = o.item_id
        JOIN card_attrs ca ON ca.item_id = ci.id
        JOIN binder b ON b.user_id = o.user_id AND b.kind = 'dex'
        WHERE o.in_binder AND ca.national_dex_no IS NOT NULL
        -- the old flag allowed two copies on one dex number in edge cases;
        -- the slot cannot, so the first wins, matching what the binder view
        -- already showed
        ON CONFLICT (binder_id, slot_key, variant) DO NOTHING
    """))

    # Happy flags, onto the slot if it exists and as a bare slot if the
    # species was flagged without a card filed.
    conn.execute(sa.text("""
        UPDATE binder_slot s SET happy = true
        FROM dex_slots d, binder b
        WHERE b.id = s.binder_id AND b.kind = 'dex'
          AND d.user_id = b.user_id AND d.happy
          AND s.slot_key = d.dex_no::text
    """))
    conn.execute(sa.text("""
        INSERT INTO binder_slot (binder_id, slot_key, happy)
        SELECT b.id, d.dex_no::text, true
        FROM dex_slots d
        JOIN binder b ON b.user_id = d.user_id AND b.kind = 'dex'
        WHERE d.happy
        ON CONFLICT (binder_id, slot_key, variant) DO NOTHING
    """))

    # --- and only now let go of the old state -------------------------------
    #
    # Every copy that was in a binder must be in a binder still. If it isn't,
    # something above is wrong and dropping the column would take the only
    # record of it with us, so raise instead and leave the database as it was.
    before = conn.execute(sa.text("""
        SELECT count(*) FROM owned o
        JOIN collection_item ci ON ci.id = o.item_id
        JOIN card_attrs ca ON ca.item_id = ci.id
        WHERE o.in_binder AND ca.national_dex_no IS NOT NULL
    """)).scalar_one()
    after = conn.execute(
        sa.text("SELECT count(*) FROM binder_slot WHERE owned_id IS NOT NULL")
    ).scalar_one()
    if after < before:
        raise RuntimeError(
            f"binder migration would lose cards: {before} were filed, "
            f"{after} arrived — leaving 0027 in place"
        )

    happy_before = conn.execute(
        sa.text("SELECT count(*) FROM dex_slots WHERE happy")
    ).scalar_one()
    happy_after = conn.execute(
        sa.text("SELECT count(*) FROM binder_slot WHERE happy")
    ).scalar_one()
    if happy_after < happy_before:
        raise RuntimeError(
            f"binder migration would lose keeper flags: {happy_before} set, "
            f"{happy_after} arrived — leaving 0027 in place"
        )

    op.drop_column("owned", "in_binder")
    op.drop_table("dex_slots")


def downgrade() -> None:
    # Rebuilt with the constraint names 0020 gave it, not the ones Alembic
    # would invent. 0020's own downgrade drops `fk_dex_slots_user` by name, so
    # a table that is merely the right shape strands the chain one step
    # further down — which is exactly where the round-trip test found it.
    op.create_table(
        "dex_slots",
        sa.Column("user_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("dex_no", sa.Integer(), nullable=False),
        sa.Column("happy", sa.Boolean(), nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("user_id", "dex_no", name="dex_slots_pkey"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_dex_slots_user", ondelete="CASCADE",
        ),
    )
    op.add_column(
        "owned",
        sa.Column("in_binder", sa.Boolean(), nullable=False, server_default="false"),
    )

    conn = op.get_bind()
    # Only the dex binder can be expressed in the old shape. Set and custom
    # binders have nowhere to go, which is the honest answer: they did not
    # exist at 0027.
    conn.execute(sa.text("""
        UPDATE owned o SET in_binder = true
        FROM binder_slot s JOIN binder b ON b.id = s.binder_id
        WHERE s.owned_id = o.id AND b.kind = 'dex'
    """))
    conn.execute(sa.text("""
        INSERT INTO dex_slots (user_id, dex_no, happy)
        SELECT b.user_id, s.slot_key::int, true
        FROM binder_slot s JOIN binder b ON b.id = s.binder_id
        WHERE b.kind = 'dex' AND s.happy AND s.slot_key ~ '^[0-9]+$'
        ON CONFLICT (user_id, dex_no) DO NOTHING
    """))

    op.drop_index("uq_binder_slot_key", table_name="binder_slot")
    op.drop_index("ix_binder_slot_owned", table_name="binder_slot")
    op.drop_index("ix_binder_slot_binder_id", table_name="binder_slot")
    op.drop_table("binder_slot")
    op.drop_index("uq_binder_one_set", table_name="binder")
    op.drop_index("uq_binder_one_dex", table_name="binder")
    op.drop_index("ix_binder_user_id", table_name="binder")
    op.drop_table("binder")
