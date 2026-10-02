from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.auth import UserProfile
from app.schemas.users import AvatarResponse, UpdateProfileRequest
from app.serializers import to_profile
from app.services import auth as auth_service
from app.services import storage

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserProfile)
async def update_me(
    body: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfile:
    await auth_service.update_username(db, user, body.username.strip())
    await db.commit()
    return to_profile(user)


@router.post("/me/avatar", response_model=AvatarResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AvatarResponse:
    data = await file.read(storage.MAX_AVATAR_BYTES + 1)
    key = await storage.save_avatar(user.id, data)
    user.avatar_url = key
    await db.commit()
    return AvatarResponse(avatar_url=storage.avatar_url(key) or "")
