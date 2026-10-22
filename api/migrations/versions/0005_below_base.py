"""Store an optional BELOW BASE bet and allow that posture on spins.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("confirmed_below_base", sa.Numeric(12, 2), nullable=True))
    op.add_column("plays", sa.Column("confirmed_below_base", sa.Numeric(12, 2), nullable=True))
    op.alter_column("plays", "active_postures", type_=sa.String(length=40), existing_nullable=False)
    op.drop_constraint("ck_spins_posture_valid", "spins", type_="check")
    op.create_check_constraint(
        "ck_spins_posture_valid",
        "spins",
        "posture IN ('base', 'press', 'max', 'early_attack', 'below_base')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_spins_posture_valid", "spins", type_="check")
    op.create_check_constraint(
        "ck_spins_posture_valid",
        "spins",
        "posture IN ('base', 'press', 'max', 'early_attack')",
    )
    op.alter_column("plays", "active_postures", type_=sa.String(length=20), existing_nullable=False)
    op.drop_column("plays", "confirmed_below_base")
    op.drop_column("sessions", "confirmed_below_base")
