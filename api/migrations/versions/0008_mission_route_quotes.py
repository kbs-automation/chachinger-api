"""Allow Mission route ids and persist pending quote snapshots.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.drop_constraint("pending_route_valid", "sessions", type_="check")
    op.alter_column(
        "sessions",
        "pending_route",
        existing_type=sa.String(length=20),
        type_=sa.String(length=40),
        existing_nullable=True,
    )
    # App validates entertainment ids + mission_to_<n>; keep DB portable (Postgres + SQLite).
    op.create_check_constraint(
        "pending_route_valid",
        "sessions",
        "pending_route IS NULL OR length(pending_route) BETWEEN 1 AND 40",
    )

    op.drop_constraint("route_valid", "plays", type_="check")
    op.alter_column(
        "plays",
        "route",
        existing_type=sa.String(length=20),
        type_=sa.String(length=40),
        existing_nullable=True,
    )
    op.create_check_constraint(
        "route_valid",
        "plays",
        "route IS NULL OR length(route) BETWEEN 1 AND 40",
    )

    op.add_column(
        "sessions",
        sa.Column("pending_quote", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sessions", "pending_quote")
    op.drop_constraint("route_valid", "plays", type_="check")
    op.alter_column(
        "plays",
        "route",
        existing_type=sa.String(length=40),
        type_=sa.String(length=20),
        existing_nullable=True,
    )
    op.create_check_constraint(
        "route_valid",
        "plays",
        "route IS NULL OR route IN ('early', 'mid', 'deep', 'extreme_deep')",
    )
    op.drop_constraint("pending_route_valid", "sessions", type_="check")
    op.alter_column(
        "sessions",
        "pending_route",
        existing_type=sa.String(length=40),
        type_=sa.String(length=20),
        existing_nullable=True,
    )
    op.create_check_constraint(
        "pending_route_valid",
        "sessions",
        "pending_route IS NULL OR pending_route IN ('early', 'mid', 'deep', 'extreme_deep')",
    )
