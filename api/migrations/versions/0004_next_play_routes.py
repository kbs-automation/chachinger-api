"""Store the pocket route chosen for the next play.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROUTE_CHECK = "pending_route IS NULL OR pending_route IN ('early', 'mid', 'deep', 'extreme_deep')"
_PLAY_ROUTE_CHECK = "route IS NULL OR route IN ('early', 'mid', 'deep', 'extreme_deep')"


def upgrade() -> None:
    op.add_column("sessions", sa.Column("pending_route", sa.String(length=20), nullable=True))
    op.create_check_constraint("pending_route_valid", "sessions", _ROUTE_CHECK)
    op.add_column("plays", sa.Column("route", sa.String(length=20), nullable=True))
    op.create_check_constraint("route_valid", "plays", _PLAY_ROUTE_CHECK)


def downgrade() -> None:
    op.drop_constraint("route_valid", "plays", type_="check")
    op.drop_column("plays", "route")
    op.drop_constraint("pending_route_valid", "sessions", type_="check")
    op.drop_column("sessions", "pending_route")
