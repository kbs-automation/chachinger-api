from typing import Any, Literal

from pydantic import Field, model_validator

from app.schemas.common import ActivePostures, MoneyIn, MoneyOut, RequestModel, ResponseModel, check_ladder
from app.schemas.decision import MissionDecisionOut

EntertainmentRouteId = Literal["early", "mid", "deep", "extreme_deep"]
BlockReason = Literal[
    "hard_exit",
    "session_not_active",
    "play_in_progress",
    "no_completed_play",
    "insufficient_balance",
    "no_qualified_mission_route",
]
PricingSource = Literal["entertainment", "mission_critical"]
LadderStatus = Literal["preliminary", "confirmed"]
PricingScope = Literal["full_route", "remaining"]


class SelectRouteRequest(RequestModel):
    route_id: str = Field(min_length=1, max_length=40)
    decision_id: str | None = Field(default=None, max_length=64)


class RouteQuoteRequest(RequestModel):
    """Reprice every route. Omit the ladder to use the session-budget reference."""

    budget: MoneyIn | None = None
    base: MoneyIn | None = None
    press: MoneyIn | None = None
    max: MoneyIn | None = None
    below_base: MoneyIn | None = None
    active_postures: ActivePostures | None = None
    # Mission remaining-cost quotes: first click still to be played (default 1).
    start_click: int | None = Field(default=None, ge=1, le=500)

    @model_validator(mode="after")
    def _ladder(self) -> "RouteQuoteRequest":
        supplied = (self.base, self.press, self.max)
        if any(v is not None for v in supplied) and not all(v is not None for v in supplied):
            raise ValueError("base, press and max must be sent together")
        if all(v is not None for v in supplied):
            check_ladder(self.base, self.press, self.max, self.active_postures, self.below_base)
        return self


class RegionWagerOut(ResponseModel):
    kind: str
    start_click: int
    end_click: int
    posture: str
    amount: MoneyOut
    clicks: int
    subtotal: MoneyOut
    safety_reason: str | None = None


class RouteCardOut(ResponseModel):
    route_id: str
    heading: str
    detail: str
    exposure_pct: float
    risk_pct: float  # Planned Balance Exposure (legacy name kept for compatibility)
    # Mission-only (null/omitted on Entertainment cards).
    end_click: int | None = None
    start_click: int | None = None
    pricing_scope: PricingScope | None = None
    total_planned_wager: MoneyOut | None = None
    planned_budget_exposure_pct: float | None = None
    planned_balance_exposure_pct: float | None = None
    regions: list[RegionWagerOut] | None = None


class RouteReferenceOut(ResponseModel):
    budget: MoneyOut
    base: MoneyOut
    press: MoneyOut
    max: MoneyOut
    below_base: MoneyOut | None = None
    source: Literal["session_budget", "quoted_bets"]
    ladder_status: LadderStatus = "preliminary"


class NextRouteResponse(ResponseModel):
    can_continue: bool
    block_reason: BlockReason | None
    completed_play_number: int | None
    next_play_number: int | None
    next_cycle_number: int | None
    prompt: str | None
    selected_route: str | None
    reference: RouteReferenceOut | None
    routes: list[RouteCardOut]
    # Present when MISSION_CRITICAL_ENGINE=true. Prefer this over inventing UX from routes[].
    decision: MissionDecisionOut | None = None
    # Offer metadata (Mission vs Entertainment pricing).
    pricing_source: PricingSource | None = None
    ladder_status: LadderStatus | None = None
    decision_id: str | None = None
    engine_version: str | None = None
    config_version: str | None = None
    parser_version: str | None = None
    # Opaque offer snapshot id for stale checks (mirrors persisted pending_quote).
    offer_meta: dict[str, Any] | None = None
