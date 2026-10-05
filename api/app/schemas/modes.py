from app.schemas.common import BetLadder, MoneyIn, MoneyOut, RequestModel, ResponseModel


class ModeOut(ResponseModel):
    """Public mode metadata. zone_map is CONFIDENTIAL and deliberately absent."""

    mode_id: str
    label: str
    min_budget: MoneyOut | None
    click_cap: int
    baseline_base: MoneyOut | None
    baseline_press: MoneyOut | None
    baseline_max: MoneyOut | None


class ExposureRequest(BetLadder):
    pass


class ExposureResponse(ResponseModel):
    mode_id: str
    exposure: MoneyOut
    required_budget: MoneyOut


class SuggestRequest(RequestModel):
    budget: MoneyIn


class SuggestResponse(ResponseModel):
    """What POST /sessions would suggest for this budget, without creating a session."""

    mode_id: str
    suggested_base: MoneyOut
    suggested_press: MoneyOut
    suggested_max: MoneyOut
    session_budget: MoneyOut
