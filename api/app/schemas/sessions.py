import uuid
from datetime import datetime

from app.schemas.common import BetLadder, MoneyIn, MoneyOut, P1ModeId, RequestModel, ResponseModel


class CreateSessionRequest(RequestModel):
    p1_mode: P1ModeId
    budget: MoneyIn


class CreateSessionResponse(ResponseModel):
    session_id: uuid.UUID
    p1_mode: str
    session_budget: MoneyOut
    current_balance: MoneyOut
    suggested_base: MoneyOut
    suggested_press: MoneyOut
    suggested_max: MoneyOut
    mode_click_cap: int
    play_number: int
    cycle_number: int


class RecalculateBudgetRequest(BetLadder):
    pass


class RecalculateBudgetResponse(ResponseModel):
    required_budget: MoneyOut
    adjusted: bool
    new_budget: MoneyOut
    current_balance: MoneyOut


class SessionOut(ResponseModel):
    id: uuid.UUID
    p1_mode: str
    status: str
    session_budget: MoneyOut
    current_balance: MoneyOut
    total_wagered: MoneyOut
    confirmed_base: MoneyOut
    confirmed_press: MoneyOut
    confirmed_max: MoneyOut
    play_count: int
    play_number: int
    cycle_number: int
    execution_grade: str | None
    started_at: datetime
    ended_at: datetime | None
