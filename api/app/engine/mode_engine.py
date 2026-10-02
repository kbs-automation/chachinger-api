"""CONFIDENTIAL. Loads zone maps from p1_mode_configs and evaluates them."""

from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import P1ModeConfig

ZONE_POSTURES = ("base", "press", "max")
CENTS = Decimal("0.01")


async def get_mode_config(db: AsyncSession, mode_id: str) -> P1ModeConfig | None:
    return await db.get(P1ModeConfig, mode_id)


async def load_zone_map(db: AsyncSession, mode_id: str) -> list[dict[str, Any]]:
    config = await get_mode_config(db, mode_id)
    if config is None:
        raise LookupError(f"no p1_mode_configs row for {mode_id}")
    return config.zone_map


def posture_at(zones: list[dict[str, Any]], click: int) -> str:
    for z in zones:
        if int(z["s"]) <= click <= int(z["e"]):
            return str(z["t"])
    return "base"


def zone_exposure(
    zones: list[dict[str, Any]], base: Decimal, press: Decimal, max_bet: Decimal
) -> Decimal:
    amounts = {"base": base, "press": press, "max": max_bet}
    total = sum(
        (Decimal(int(z["e"]) - int(z["s"]) + 1) * amounts.get(z["t"], base) for z in zones),
        Decimal("0"),
    )
    return total.quantize(CENTS)


def validate_zone_map(zones: Any, click_cap: int) -> list[str]:
    """Returns a list of problems; empty means the map covers 1..click_cap with no gaps."""
    if not isinstance(zones, list) or not zones:
        return ["zone_map must be a non-empty list"]
    errors: list[str] = []
    expected = 1
    for i, z in enumerate(zones):
        if not isinstance(z, dict) or not {"s", "e", "t"} <= z.keys():
            errors.append(f"zone {i} must have s, e and t")
            continue
        try:
            s, e = int(z["s"]), int(z["e"])
        except (TypeError, ValueError):
            errors.append(f"zone {i} has non-integer bounds")
            continue
        if z["t"] not in ZONE_POSTURES:
            errors.append(f"zone {i} has invalid posture {z['t']!r}")
        if s != expected:
            errors.append(f"zone {i} starts at {s}, expected {expected}")
        if e < s:
            errors.append(f"zone {i} ends before it starts")
        expected = e + 1
    if expected != click_cap + 1:
        errors.append(f"zone_map covers clicks 1–{expected - 1}, expected 1–{click_cap}")
    return errors
