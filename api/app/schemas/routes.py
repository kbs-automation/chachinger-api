from typing import Literal

from pydantic import model_validator

from app.schemas.common import ActivePostures, MoneyIn, MoneyOut, RequestModel, ResponseModel, check_ladder

RouteId = Literal["early", "mid", "deep", "extreme_deep"]
BlockReason = Literal[
    "hard_exit",
    "session_not_active",
    "play_in_progress",
    "no_completed_play",
    "insufficient_balance",
]


class SelectRouteRequest(RequestModel):
    route_id: RouteId


class RouteQuoteRequest(RequestModel):
    """Reprice every route. Omit the ladder to use the session-budget reference."""

    budget: MoneyIn | None = None
    base: MoneyIn | None = None
    press: MoneyIn | None = None
    max: MoneyIn | None = None
    active_postures: ActivePostures | None = None

    @model_validator(mode="after")
    def _ladder(self) -> "RouteQuoteRequest":
        supplied = (self.base, self.press, self.max)
        if any(v is not None for v in supplied) and not all(v is not None for v in supplied):
            raise ValueError("base, press and max must be sent together")
        if all(v is not None for v in supplied):
            check_ladder(self.base, self.press, self.max, self.active_postures)
        return self


class RouteCardOut(ResponseModel):
    route_id: RouteId
    heading: str
    detail: str
    exposure_pct: float
    risk_pct: float


class RouteReferenceOut(ResponseModel):
    budget: MoneyOut
    base: MoneyOut
    press: MoneyOut
    max: MoneyOut
    source: Literal["session_budget", "quoted_bets"]


class NextRouteResponse(ResponseModel):
    can_continue: bool
    block_reason: BlockReason | None
    completed_play_number: int | None
    next_play_number: int | None
    next_cycle_number: int | None
    prompt: str | None
    selected_route: RouteId | None
    reference: RouteReferenceOut | None
    routes: list[RouteCardOut]
