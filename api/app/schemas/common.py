from decimal import Decimal
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, model_validator

from app.engine import postures

MoneyOut = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
MoneyIn = Annotated[Decimal, Field(gt=0, le=1_000_000, max_digits=12, decimal_places=2)]

P1ModeId = Literal["entertainment", "entertainment_plus", "strike", "pursuit", "deep_run_pro"]
Posture = Literal["base", "press", "max", "early_attack", "below_base"]
LadderPosture = Literal["below_base", "base", "press", "max"]
ActivePostures = Annotated[list[LadderPosture], Field(min_length=2, max_length=4)]
Tier = Literal["vip", "black", "elite", "diamond"]

T = TypeVar("T")


class RequestModel(BaseModel):
    """Unknown fields are rejected, so e.g. session_budget can never be smuggled in."""

    model_config = ConfigDict(extra="forbid")


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def check_ladder(
    base: Decimal,
    press: Decimal,
    max_bet: Decimal,
    active: list[str] | None,
    below_base: Decimal | None = None,
) -> tuple[str, ...]:
    if active is not None and "below_base" in active and below_base is None:
        raise ValueError("below_base amount is required when that posture is active")
    chosen = postures.chosen(active, below_base)
    if not postures.ordered(base, press, max_bet, chosen, below_base):
        raise ValueError("active bets must satisfy below_base ≤ base ≤ press ≤ max")
    return chosen


class BetLadder(RequestModel):
    base: MoneyIn
    press: MoneyIn
    max: MoneyIn
    # Optional. When active, map clicks that would be BASE are played at this amount.
    below_base: MoneyIn | None = None
    # Omitted means base, press and max. Amounts for a switched-off posture are ignored.
    active_postures: ActivePostures | None = None

    @model_validator(mode="after")
    def _ordered(self) -> "BetLadder":
        check_ladder(self.base, self.press, self.max, self.active_postures, self.below_base)
        return self

    @property
    def chosen_postures(self) -> tuple[str, ...]:
        return postures.chosen(self.active_postures, self.below_base)


class Page(ResponseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class MessageResponse(ResponseModel):
    status: str
