import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.dependencies import get_current_user, user_rate_limit
from app.models import Spin, User
from app.routers.plays import load_owned_play
from app.schemas.spins import SpinResponse, SpinResultRequest, SpinResultResponse
from app.services import engine
from app.services.errors import DomainError, not_found

router = APIRouter(prefix="/plays/{play_id}/spins", tags=["spins"])


@router.post(
    "",
    response_model=SpinResponse,
    dependencies=[Depends(user_rate_limit("spins", 120, 60))],
)
async def register_spin(
    play_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SpinResponse:
    play, session = await load_owned_play(db, user, play_id, for_update=True)
    outcome = await engine.process_spin(db, play, session)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise DomainError(409, "concurrent_spin", "Another spin was registered at once") from exc
    return SpinResponse(
        spin_id=outcome.spin.id if outcome.spin else None,
        posture=outcome.posture,
        next_bet_amount=outcome.bet_amount,
        play_progress_pct=outcome.progress_pct,
        play_number=play.play_number,
        cycle_number=play.cycle_number,
        at_hard_exit_cap=outcome.at_hard_exit_cap,
        current_balance=session.current_balance,
        redirect=outcome.redirect,
    )


@router.post("/{spin_id}/result", response_model=SpinResultResponse)
async def submit_result(
    play_id: uuid.UUID,
    spin_id: uuid.UUID,
    body: SpinResultRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SpinResultResponse:
    play, session = await load_owned_play(db, user, play_id, for_update=True)
    spin = await db.scalar(
        select(Spin).where(Spin.id == spin_id, Spin.play_id == play.id).with_for_update()
    )
    if spin is None:
        raise not_found("spin")
    bonus_win = Decimal(str(body.win_amount)) if body.win_amount is not None else None
    outcome = await engine.submit_result(db, play, session, spin, body.result, bonus_win)
    await db.commit()
    return SpinResultResponse(
        qualifying=outcome.qualifying,
        win_amount=outcome.win_amount,
        current_balance=session.current_balance,
        redirect=outcome.redirect,
        play_number=play.play_number,
        cycle_number=play.cycle_number,
    )
