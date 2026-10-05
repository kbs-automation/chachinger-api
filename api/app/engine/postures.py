"""Posture selection: a player may switch off one of BASE/PRESS/MAX for a play.

Clicks in a switched-off zone are played at the nearest active posture below it,
or above it when nothing below is active (same rule as the mobile app).
"""

from collections.abc import Iterable
from decimal import Decimal

POSTURE_ORDER: tuple[str, ...] = ("base", "press", "max")
ALL_POSTURES = ",".join(POSTURE_ORDER)
MIN_ACTIVE = 2


def normalize(active: Iterable[str] | None) -> tuple[str, ...]:
    if active is None:
        return POSTURE_ORDER
    chosen = set(active)
    unknown = chosen - set(POSTURE_ORDER)
    if unknown:
        raise ValueError(f"unknown postures: {sorted(unknown)}")
    if len(chosen) < MIN_ACTIVE:
        raise ValueError(f"at least {MIN_ACTIVE} postures must stay active")
    return tuple(p for p in POSTURE_ORDER if p in chosen)


def to_column(active: Iterable[str] | None) -> str:
    return ",".join(normalize(active))


def from_column(value: str | None) -> tuple[str, ...]:
    if not value:
        return POSTURE_ORDER
    return normalize(v for v in value.split(",") if v)


def effective(posture: str, active: tuple[str, ...]) -> str:
    if posture in active or posture not in POSTURE_ORDER:
        return posture
    i = POSTURE_ORDER.index(posture)
    for p in reversed(POSTURE_ORDER[:i]):
        if p in active:
            return p
    for p in POSTURE_ORDER[i + 1 :]:
        if p in active:
            return p
    return posture


def effective_amounts(
    base: Decimal, press: Decimal, max_bet: Decimal, active: tuple[str, ...]
) -> tuple[Decimal, Decimal, Decimal]:
    amounts = {"base": base, "press": press, "max": max_bet}
    return (
        amounts[effective("base", active)],
        amounts[effective("press", active)],
        amounts[effective("max", active)],
    )


def ordered(base: Decimal, press: Decimal, max_bet: Decimal, active: tuple[str, ...]) -> bool:
    """Active postures must not descend; switched-off ones are ignored."""
    amounts = {"base": base, "press": press, "max": max_bet}
    values = [amounts[p] for p in active]
    return all(a <= b for a, b in zip(values, values[1:], strict=False))
