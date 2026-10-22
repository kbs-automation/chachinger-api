"""Posture selection: a player may switch off one of BASE/PRESS/MAX for a play.

Clicks in a switched-off zone are played at the nearest active posture below it,
or above it when nothing below is active (same rule as the mobile app).
"""

from collections.abc import Iterable
from decimal import Decimal

POSTURE_ORDER: tuple[str, ...] = ("below_base", "base", "press", "max")
DEFAULT_ACTIVE: tuple[str, ...] = ("base", "press", "max")
ALL_POSTURES = ",".join(DEFAULT_ACTIVE)
MIN_ACTIVE = 2


def normalize(active: Iterable[str] | None, *, include_below_base: bool = False) -> tuple[str, ...]:
    if active is None:
        chosen = ["below_base", *DEFAULT_ACTIVE] if include_below_base else list(DEFAULT_ACTIVE)
        return tuple(chosen)
    selected = set(active)
    unknown = selected - set(POSTURE_ORDER)
    if unknown:
        raise ValueError(f"unknown postures: {sorted(unknown)}")
    if len(selected) < MIN_ACTIVE:
        raise ValueError(f"at least {MIN_ACTIVE} postures must stay active")
    return tuple(p for p in POSTURE_ORDER if p in selected)


def chosen(active: Iterable[str] | None, below_base: Decimal | None) -> tuple[str, ...]:
    """Active set for a ladder. An omitted list plus a BELOW BASE amount turns that posture on."""
    include = below_base is not None and (active is None or "below_base" in set(active))
    return normalize(active, include_below_base=include)


def to_column(active: Iterable[str] | None) -> str:
    return ",".join(normalize(active))


def from_column(value: str | None) -> tuple[str, ...]:
    if not value:
        return DEFAULT_ACTIVE
    return normalize(v for v in value.split(",") if v)


def resolve(map_posture: str, active: tuple[str, ...], *, below_base_enabled: bool) -> str:
    """Map posture after toggles. An active BELOW BASE amount replaces BASE."""
    resolved = effective(map_posture, active)
    if below_base_enabled and resolved == "base" and "below_base" in active:
        return "below_base"
    return resolved


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


def ordered(
    base: Decimal,
    press: Decimal,
    max_bet: Decimal,
    active: tuple[str, ...],
    below_base: Decimal | None = None,
) -> bool:
    """Active postures must not descend; switched-off ones are ignored."""
    amounts = {"below_base": below_base, "base": base, "press": press, "max": max_bet}
    values: list[Decimal] = []
    for posture in active:
        amount = amounts[posture]
        if amount is None:
            return False
        values.append(amount)
    return all(left <= right for left, right in zip(values, values[1:], strict=False))
