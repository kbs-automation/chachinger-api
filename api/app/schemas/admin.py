"""Admin-only schemas.

click_number appears ONLY in AdminSpinOut, AdminPlayOut and LiveSessionOut.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import EmailStr, Field, field_validator

from app.schemas.common import MoneyOut, RequestModel, ResponseModel


class AdminLoginRequest(RequestModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class AdminTokenResponse(ResponseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class DashboardOut(ResponseModel):
    total_users: int
    active_subscribers: int
    trialing_subscribers: int
    subscribers_by_tier: dict[str, int]
    mrr: float
    active_sessions_now: int
    sessions_today: int
    engine_started_at: datetime
    engine_uptime_seconds: int


class AdminUserRow(ResponseModel):
    id: uuid.UUID
    player_number: str
    username: str
    email: str
    tier: str
    subscription_status: str | None
    joined_at: datetime
    last_session_at: datetime | None
    execution_grade: str | None
    status: str
    is_flagged: bool
    is_suspended: bool


class AdminUserStatus(ResponseModel):
    id: uuid.UUID
    is_flagged: bool
    is_suspended: bool


class SuspendRequest(RequestModel):
    suspended: bool = True
    reason: str | None = Field(default=None, max_length=500)


class AdminSpinOut(ResponseModel):
    id: uuid.UUID
    click_number: int
    posture: str
    bet_amount: MoneyOut
    result_input: str | None
    is_qualifying: bool
    spun_at: datetime


class AdminPlayOut(ResponseModel):
    id: uuid.UUID
    play_number: int
    cycle_number: int
    p1_mode: str | None
    p1_mode_active: bool
    click_number: int
    click_cap: int
    confirmed_base: MoneyOut
    confirmed_press: MoneyOut
    confirmed_max: MoneyOut
    qualifying_result: MoneyOut | None
    result_type: str | None
    win_amount: MoneyOut
    status: str
    started_at: datetime
    ended_at: datetime | None
    spins: list[AdminSpinOut]


class AdminSessionOut(ResponseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    p1_mode: str
    status: str
    session_budget: MoneyOut
    current_balance: MoneyOut
    total_wagered: MoneyOut
    confirmed_base: MoneyOut
    confirmed_press: MoneyOut
    confirmed_max: MoneyOut
    play_count: int
    cycle_number: int
    execution_grade: str | None
    started_at: datetime
    ended_at: datetime | None


class AdminSessionDetail(ResponseModel):
    session: AdminSessionOut
    user: dict[str, Any]
    plays: list[AdminPlayOut]


class LiveSessionOut(ResponseModel):
    session_id: uuid.UUID
    user_id: uuid.UUID
    player_number: str
    username: str
    p1_mode: str
    session_budget: MoneyOut
    current_balance: MoneyOut
    total_wagered: MoneyOut
    play_count: int
    play_id: uuid.UUID | None
    play_number: int | None
    cycle_number: int
    click_number: int | None
    click_cap: int | None
    p1_mode_active: bool
    started_at: datetime


class AdminModeOut(ResponseModel):
    """Zone maps are never serialized, even to admins (Rule 9); only their shape is reported."""

    mode_id: str
    label: str
    sort_order: int
    click_cap: int
    min_budget: MoneyOut | None
    baseline_base: MoneyOut | None
    baseline_press: MoneyOut | None
    baseline_max: MoneyOut | None
    is_active: bool
    zone_count: int


class ZoneIn(RequestModel):
    s: int = Field(ge=1)
    e: int = Field(ge=1)
    t: Literal["base", "press", "max"]


class ModeUpdateRequest(RequestModel):
    label: str | None = Field(default=None, min_length=1, max_length=64)
    is_active: bool | None = None
    min_budget: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    baseline_base: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    baseline_press: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    baseline_max: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    zone_map: list[ZoneIn] | None = None

    @field_validator("label", "is_active", "zone_map")
    @classmethod
    def _not_null(cls, v: Any) -> Any:
        if v is None:
            raise ValueError("may be omitted but not null")
        return v


class ConfigUpdateRequest(RequestModel):
    values: dict[str, Any]


class EngineConfigOut(ResponseModel):
    values: dict[str, Any]


class AuditLogOut(ResponseModel):
    id: uuid.UUID
    admin_user_id: uuid.UUID
    action: str
    target_type: str | None
    target_id: str | None
    payload: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime
