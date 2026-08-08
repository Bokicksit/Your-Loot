"""The box is its own question.

LEGO completeness used to fold two independent facts into one word:
"complete+box", "complete+instructions", "box". Whether you kept the box and
what state the set is in are not the same question — you can have a built
display piece with the box in the loft, or a sealed one where the box *is* the
point — so they become a checkbox and a dropdown.

The states collapse to five: sealed, open, loose, built, incomplete. Sealed
implies the box, and the app enforces that; the rest are free either way.

Three old values have no equivalent, because they described owning a piece of
a set rather than a set: `parts`, `instructions` and `box`. They mapped to the
nearest honest thing below. They were also what made a LEGO acquisition count
as "spare parts" and leave the set on the wanted list, so anyone who used them
should look at those rows.

Revision ID: 0022
Revises: 0021
"""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

# old lego value -> (new completeness, has_box)
REMAP = {
    "sealed": ("sealed", True),
    "complete+box": ("open", True),
    "complete+instructions": ("open", False),
    "complete": ("loose", False),
    "incomplete": ("incomplete", False),
    # the three that described part of a set rather than a set
    "parts": ("loose", False),
    "instructions": ("loose", False),
    "box": ("open", True),
}


def upgrade() -> None:
    op.add_column("owned", sa.Column("has_box", sa.Boolean(), nullable=True))

    for old, (new, boxed) in REMAP.items():
        op.execute(
            sa.text(
                """
                UPDATE owned SET completeness = :new, has_box = :boxed
                WHERE completeness = :old
                  AND item_id IN (SELECT id FROM collection_item WHERE module = 'lego')
                """
            ).bindparams(new=new, boxed=boxed, old=old)
        )


def downgrade() -> None:
    # Best effort: the pair carries more than the single word did, so the two
    # box-less states that used to be distinguishable collapse together.
    op.execute(
        """
        UPDATE owned SET completeness = CASE
            WHEN completeness = 'sealed' THEN 'sealed'
            WHEN completeness = 'open' AND has_box THEN 'complete+box'
            WHEN completeness = 'open' THEN 'complete+instructions'
            WHEN completeness = 'built' AND has_box THEN 'complete+box'
            WHEN completeness = 'built' THEN 'complete'
            WHEN completeness = 'loose' THEN 'complete'
            WHEN completeness = 'incomplete' THEN 'incomplete'
            ELSE completeness
        END
        WHERE item_id IN (SELECT id FROM collection_item WHERE module = 'lego')
        """
    )
    op.drop_column("owned", "has_box")
