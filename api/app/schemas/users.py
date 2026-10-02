from pydantic import Field

from app.schemas.auth import USERNAME_PATTERN
from app.schemas.common import RequestModel, ResponseModel


class UpdateProfileRequest(RequestModel):
    username: str = Field(min_length=2, max_length=32, pattern=USERNAME_PATTERN)


class AvatarResponse(ResponseModel):
    avatar_url: str
