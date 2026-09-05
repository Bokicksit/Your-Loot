"""A pocket in a binder of your own can carry a section name.

"Charizards", "Trades", "Doubles": a real binder with more than one thing in
it gets a divider tab where each run begins. Here that is a word on the pocket
where the section starts. The pocket can be empty — a divider card — or hold
the first card of the run and wear the name as a tab; either way it moves with
Arrange like any other pocket, because it is one.

Revision ID: 0056
Revises: 0055
"""

import sqlalchemy as sa
from alembic import op

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("binder_slot", sa.Column("section", sa.String(60), nullable=True))


def downgrade() -> None:
    op.drop_column("binder_slot", "section")
