from app.schemas.common import BetLadder, MoneyOut, ResponseModel


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
