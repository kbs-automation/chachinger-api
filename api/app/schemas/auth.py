import uuid
from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas.common import RequestModel, ResponseModel

USERNAME_PATTERN = r"^[A-Za-z0-9_.\- ]+$"


class RegisterRequest(RequestModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    username: str | None = Field(
        default=None, min_length=2, max_length=32, pattern=USERNAME_PATTERN
    )


class LoginRequest(RequestModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class RefreshRequest(RequestModel):
    refresh_token: str | None = None


class UserProfile(ResponseModel):
    id: uuid.UUID
    player_number: str
    username: str
    email: str
    avatar_url: str | None
    tier: str
    subscription_status: str | None
    created_at: datetime
    last_login_at: datetime | None


class TokenResponse(ResponseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthResponse(TokenResponse):
    user: UserProfile
