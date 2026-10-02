from decimal import Decimal
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, model_validator

MoneyOut = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
MoneyIn = Annotated[Decimal, Field(gt=0, le=1_000_000, max_digits=12, decimal_places=2)]

P1ModeId = Literal["entertainment", "entertainment_plus", "strike", "pursuit", "deep_run_pro"]
Posture = Literal["base", "press", "max", "early_attack"]
Tier = Literal["vip", "black", "elite", "diamond"]

T = TypeVar("T")


class RequestModel(BaseModel):
    """Unknown fields are rejected, so e.g. session_budget can never be smuggled in."""

    model_config = ConfigDict(extra="forbid")


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BetLadder(RequestModel):
    base: MoneyIn
    press: MoneyIn
    max: MoneyIn

    @model_validator(mode="after")
    def _ordered(self) -> "BetLadder":
        if not self.base <= self.press <= self.max:
            raise ValueError("bets must satisfy base ≤ press ≤ max")
        return self


class Page(ResponseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class MessageResponse(ResponseModel):
    status: str
