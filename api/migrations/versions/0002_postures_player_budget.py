"""Posture selection per play and the player's requested budget per session.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "plays",
        sa.Column(
            "active_postures",
            sa.String(20),
            nullable=False,
            server_default="base,press,max",
        ),
    )
    op.add_column("sessions", sa.Column("player_budget", sa.Numeric(12, 2)))


def downgrade() -> None:
    op.drop_column("sessions", "player_budget")
    op.drop_column("plays", "active_postures")
