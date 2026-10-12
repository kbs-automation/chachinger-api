"""Replace the incorrect Entertainment zone map with the approved Flutter map.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-12
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.engine.zone_maps import ENTERTAINMENT_ZONES

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Prior incorrect seed (1–6 BASE …). Kept only so downgrade can restore it.
_OLD_ENTERTAINMENT_ZONES = [
    {"s": 1, "e": 6, "t": "base"},
    {"s": 7, "e": 13, "t": "press"},
    {"s": 14, "e": 16, "t": "base"},
    {"s": 17, "e": 19, "t": "press"},
    {"s": 20, "e": 33, "t": "press"},
    {"s": 34, "e": 39, "t": "base"},
    {"s": 40, "e": 42, "t": "press"},
    {"s": 43, "e": 55, "t": "max"},
    {"s": 56, "e": 59, "t": "press"},
    {"s": 60, "e": 64, "t": "max"},
    {"s": 65, "e": 79, "t": "base"},
    {"s": 80, "e": 96, "t": "press"},
]


def _set_entertainment_map(zones: list[dict]) -> None:
    zone_map = sa.cast(sa.literal(json.dumps(zones), sa.Text()), postgresql.JSONB)
    op.execute(
        sa.table(
            "p1_mode_configs",
            sa.column("mode_id", sa.String),
            sa.column("zone_map", postgresql.JSONB),
        )
        .update()
        .where(sa.column("mode_id") == "entertainment")
        .values(zone_map=zone_map)
    )


def upgrade() -> None:
    _set_entertainment_map(ENTERTAINMENT_ZONES)


def downgrade() -> None:
    _set_entertainment_map(_OLD_ENTERTAINMENT_ZONES)
