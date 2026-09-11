"""period_settlements.settled_with — months paid off by one payment

Revision ID: 0034
Revises: 0033
Create Date: 2026-09-11 00:00:00.000000

Several open months can be closed with a single transfer. Each month still
gets its own record, so everything that reads one month keeps working; this
column names the run it was closed with (``2026-06..2026-08``) so reopening
one month reopens the whole run — the payment covered all of them at once.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "period_settlements",
        sa.Column("settled_with", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("period_settlements", "settled_with")
