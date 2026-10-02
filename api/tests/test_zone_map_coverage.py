from decimal import Decimal

import pytest
from sqlalchemy import select

from app.engine import mode_engine, zone_maps
from app.models import P1ModeConfig


@pytest.mark.parametrize("seed", zone_maps.MODE_SEEDS, ids=lambda s: s["mode_id"])
def test_seed_zone_map_covers_exactly_1_to_96(seed):
    assert seed["click_cap"] == 96
    assert mode_engine.validate_zone_map(seed["zone_map"], 96) == []
    clicks = [c for z in seed["zone_map"] for c in range(z["s"], z["e"] + 1)]
    assert clicks == list(range(1, 97))


def test_standard_map_covers_1_to_96():
    assert mode_engine.validate_zone_map(zone_maps.ENTERTAINMENT_ZONES, 96) == []


async def test_database_zone_maps_cover_1_to_96(db):
    rows = (await db.scalars(select(P1ModeConfig))).all()
    assert {r.mode_id for r in rows} == {
        "entertainment",
        "entertainment_plus",
        "strike",
        "pursuit",
        "deep_run_pro",
    }
    for row in rows:
        assert row.click_cap == 96
        assert mode_engine.validate_zone_map(row.zone_map, row.click_cap) == [], row.mode_id


def test_validator_detects_gaps_overlaps_and_short_maps():
    assert mode_engine.validate_zone_map([{"s": 1, "e": 95, "t": "base"}], 96)
    assert mode_engine.validate_zone_map(
        [{"s": 1, "e": 50, "t": "base"}, {"s": 50, "e": 96, "t": "max"}], 96
    )
    assert mode_engine.validate_zone_map(
        [{"s": 1, "e": 40, "t": "base"}, {"s": 42, "e": 96, "t": "max"}], 96
    )
    assert mode_engine.validate_zone_map([{"s": 1, "e": 96, "t": "turbo"}], 96)


@pytest.mark.parametrize(
    ("zones", "expected"),
    [
        (zone_maps.STRIKE_ZONES, Decimal("890")),
        (zone_maps.PURSUIT_ZONES, Decimal("890")),
        (zone_maps.DEEP_RUN_PRO_ZONES, Decimal("935")),
    ],
)
def test_baseline_exposures(zones, expected):
    assert mode_engine.zone_exposure(zones, Decimal(5), Decimal(10), Decimal(30)) == expected
