"""CONFIDENTIAL. Risk Unit formula used by the standard (P2+) engine."""

from decimal import ROUND_DOWN, Decimal

LADDER = [1, 2, 3, 4, 5, 6, 8, 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100]
BASE_FACTOR = Decimal("0.40")
PRESS_FACTOR = Decimal("1.00")
MAX_FACTOR = Decimal("1.40")
CENTS = Decimal("0.01")


def snap(v: Decimal) -> Decimal:
    if v < 1:
        return v.quantize(CENTS)
    return Decimal(min(LADDER, key=lambda x: abs(x - v)))


def risk_unit(budget: Decimal) -> Decimal:
    return budget / 100 if budget > 0 else Decimal("0")


def calc_ru_bets(budget: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    ru = risk_unit(budget)
    return snap(ru * BASE_FACTOR), snap(ru * PRESS_FACTOR), snap(ru * MAX_FACTOR)


def money_down(v: Decimal) -> Decimal:
    return v.quantize(CENTS, rounding=ROUND_DOWN)
