import uuid

from pydantic import model_validator

from app.engine import postures
from app.schemas.common import (
    ActivePostures,
    MoneyIn,
    MoneyOut,
    Posture,
    RequestModel,
    ResponseModel,
    check_ladder,
)


class StartPlayRequest(RequestModel):
    confirmed_base: MoneyIn
    confirmed_press: MoneyIn
    confirmed_max: MoneyIn
    confirmed_below_base: MoneyIn | None = None
    active_postures: ActivePostures | None = None

    @model_validator(mode="after")
    def _ordered(self) -> "StartPlayRequest":
        check_ladder(
            self.confirmed_base,
            self.confirmed_press,
            self.confirmed_max,
            self.active_postures,
            self.confirmed_below_base,
        )
        return self

    @property
    def chosen_postures(self) -> tuple[str, ...]:
        return postures.chosen(self.active_postures, self.confirmed_below_base)


class PlayStartResponse(ResponseModel):
    play_id: uuid.UUID
    status: str
    posture: Posture
    next_bet_amount: MoneyOut
    play_progress_pct: int
    play_number: int
    cycle_number: int
    click_cap: int
    current_balance: MoneyOut
    session_budget: MoneyOut
    confirmed_below_base: MoneyOut | None = None


class PlayStateResponse(ResponseModel):
    play_id: uuid.UUID
    status: str
    posture: Posture
    next_bet_amount: MoneyOut
    play_progress_pct: int
    play_number: int
    cycle_number: int
    result_type: str | None
    win_amount: MoneyOut
    current_balance: MoneyOut
