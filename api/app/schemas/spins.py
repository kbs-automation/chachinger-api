import uuid
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.common import MoneyOut, Posture, RequestModel, ResponseModel

RESULT_INPUT_PATTERN = r"(?i)^(bonus|\d+(\.\d+)?x?)$"


class SpinResponse(ResponseModel):
    """Spin Response Contract (section 4.5) plus spin_id/redirect. Never contains click data."""

    spin_id: uuid.UUID | None
    posture: Posture
    next_bet_amount: MoneyOut
    play_progress_pct: int
    play_number: int
    cycle_number: int
    at_hard_exit_cap: bool
    current_balance: MoneyOut
    redirect: Literal["continue", "hard_exit"]


class SpinResultRequest(RequestModel):
    """Either a result ("34x" or "bonus") or the dollar amount the machine paid.

    A bare win_amount is converted to a multiplier of the spin's bet. With "bonus" the
    win_amount is the bonus payout. With a multiplier it must be omitted.
    """

    result: str | None = Field(
        default=None, min_length=1, max_length=20, pattern=RESULT_INPUT_PATTERN
    )
    win_amount: float | None = Field(default=None, gt=0, le=10_000_000)

    @model_validator(mode="after")
    def _one_input(self) -> "SpinResultRequest":
        if self.result is None and self.win_amount is None:
            raise ValueError("provide result or win_amount")
        is_bonus = self.result is not None and self.result.strip().lower() == "bonus"
        if self.result is not None and not is_bonus and self.win_amount is not None:
            raise ValueError("win_amount is only allowed alone or with a bonus result")
        return self


class SpinResultResponse(ResponseModel):
    qualifying: bool
    win_amount: MoneyOut
    multiplier: MoneyOut | None
    current_balance: MoneyOut
    redirect: Literal["next_play", "hard_exit", "continue"]
    play_number: int
    cycle_number: int


class UndoSpinResponse(ResponseModel):
    """The play after its latest spin was reversed. posture/bet_amount describe the spin
    that is now the latest one (or the opening spin when none are left)."""

    posture: Posture
    bet_amount: MoneyOut
    has_spins: bool
    play_progress_pct: int
    play_number: int
    cycle_number: int
    current_balance: MoneyOut
