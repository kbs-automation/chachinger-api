import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.dependencies import get_current_user
from app.models import GameSession, Play, User
from app.schemas.plays import PlayStartResponse, PlayStateResponse, StartPlayRequest
from app.services import engine, play_tracker
from app.services import sessions as session_service
from app.services.errors import not_found

router = APIRouter(tags=["plays"])


async def load_owned_play(
    db: AsyncSession, user: User, play_id: uuid.UUID, for_update: bool = False
) -> tuple[Play, GameSession]:
    stmt = select(Play).where(Play.id == play_id, Play.user_id == user.id)
    if for_update:
        stmt = stmt.with_for_update()
    play = await db.scalar(stmt)
    if play is None:
        raise not_found("play")
    session_stmt = select(GameSession).where(GameSession.id == play.session_id)
    if for_update:
        session_stmt = session_stmt.with_for_update()
    session = await db.scalar(session_stmt)
    if session is None:
        raise not_found("session")
    return play, session


async def play_state(db: AsyncSession, play: Play, session: GameSession) -> PlayStateResponse:
    posture, bet = await engine.upcoming_bet(db, play)
    return PlayStateResponse(
        play_id=play.id,
        status=play.status,
        posture=posture,
        next_bet_amount=bet,
        play_progress_pct=engine.progress_pct(play.total_clicks, play.click_cap),
        play_number=play.play_number,
        cycle_number=play.cycle_number,
        result_type=play.result_type,
        win_amount=play.win_amount,
        current_balance=session.current_balance,
    )


@router.post(
    "/sessions/{session_id}/plays",
    response_model=PlayStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_play(
    session_id: uuid.UUID,
    body: StartPlayRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlayStartResponse:
    session = await session_service.get_owned_session(db, user, session_id, for_update=True)
    play = await play_tracker.start_play(
        db, session, body.confirmed_base, body.confirmed_press, body.confirmed_max
    )
    posture, bet = await engine.upcoming_bet(db, play)
    await db.commit()
    return PlayStartResponse(
        play_id=play.id,
        status=play.status,
        posture=posture,
        next_bet_amount=bet,
        play_progress_pct=0,
        play_number=play.play_number,
        cycle_number=play.cycle_number,
        click_cap=play.click_cap,
        current_balance=session.current_balance,
    )


@router.get("/plays/{play_id}", response_model=PlayStateResponse)
async def get_play(
    play_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlayStateResponse:
    play, session = await load_owned_play(db, user, play_id)
    return await play_state(db, play, session)


@router.post("/plays/{play_id}/end", response_model=PlayStateResponse)
async def end_play(
    play_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlayStateResponse:
    play, session = await load_owned_play(db, user, play_id, for_update=True)
    engine.end_play_manually(play, session)
    await db.commit()
    return await play_state(db, play, session)
