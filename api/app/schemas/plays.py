import uuid

from pydantic import model_validator

from app.schemas.common import MoneyIn, MoneyOut, Posture, RequestModel, ResponseModel


class StartPlayRequest(RequestModel):
    confirmed_base: MoneyIn
    confirmed_press: MoneyIn
    confirmed_max: MoneyIn

    @model_validator(mode="after")
    def _ordered(self) -> "StartPlayRequest":
        if not self.confirmed_base <= self.confirmed_press <= self.confirmed_max:
            raise ValueError("bets must satisfy base ≤ press ≤ max")
        return self


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
