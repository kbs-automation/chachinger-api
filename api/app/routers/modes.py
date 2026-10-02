from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.common import P1ModeId
from app.schemas.modes import ExposureRequest, ExposureResponse, ModeOut
from app.services import budget, modes

router = APIRouter(prefix="/modes", tags=["modes"])


@router.get("", response_model=list[ModeOut])
async def list_modes(db: AsyncSession = Depends(get_db)) -> list[ModeOut]:
    return [ModeOut.model_validate(m) for m in await modes.list_active_modes(db)]


@router.post("/{mode_id}/exposure", response_model=ExposureResponse)
async def mode_exposure(
    mode_id: P1ModeId,
    body: ExposureRequest,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExposureResponse:
    result = await budget.calc_96_exposure(db, mode_id, body.base, body.press, body.max)
    return ExposureResponse(
        mode_id=mode_id, exposure=result.exposure, required_budget=result.required_budget
    )
