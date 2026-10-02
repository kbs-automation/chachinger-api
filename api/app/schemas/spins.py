import uuid
from typing import Literal

from pydantic import Field

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
    result: str = Field(min_length=1, max_length=20, pattern=RESULT_INPUT_PATTERN)
    # Only honored for "bonus": a bonus has no multiplier, so its payout is entered directly.
    win_amount: float | None = Field(default=None, ge=0, le=10_000_000)


class SpinResultResponse(ResponseModel):
    qualifying: bool
    win_amount: MoneyOut
    current_balance: MoneyOut
    redirect: Literal["next_play", "hard_exit", "continue"]
    play_number: int
    cycle_number: int
