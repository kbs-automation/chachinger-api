import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.common import Page
from app.schemas.sessions import (
    CreateSessionRequest,
    CreateSessionResponse,
    RecalculateBudgetRequest,
    RecalculateBudgetResponse,
    SessionOut,
)
from app.serializers import to_session_out
from app.services import budget, engine, play_tracker
from app.services import sessions as session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=CreateSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: CreateSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CreateSessionResponse:
    created = await session_service.create_session(db, user, body.p1_mode, body.budget)
    await db.commit()
    s = created.session
    return CreateSessionResponse(
        session_id=s.id,
        p1_mode=s.p1_mode,
        session_budget=s.session_budget,
        current_balance=s.current_balance,
        suggested_base=created.suggested_base,
        suggested_press=created.suggested_press,
        suggested_max=created.suggested_max,
        mode_click_cap=created.mode_click_cap,
        play_number=1,
        cycle_number=1,
    )


@router.post("/{session_id}/recalculate-budget", response_model=RecalculateBudgetResponse)
async def recalculate_budget(
    session_id: uuid.UUID,
    body: RecalculateBudgetRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RecalculateBudgetResponse:
    session = await session_service.get_owned_session(db, user, session_id, for_update=True)
    result = await budget.recalculate_session_budget(db, session, body.base, body.press, body.max)
    await db.commit()
    return RecalculateBudgetResponse(
        required_budget=result.required_budget,
        adjusted=result.adjusted,
        new_budget=result.new_budget,
        current_balance=result.current_balance,
    )


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionOut:
    return to_session_out(await session_service.get_owned_session(db, user, session_id))


@router.post("/{session_id}/end", response_model=SessionOut)
async def end_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionOut:
    session = await session_service.get_owned_session(db, user, session_id, for_update=True)
    active = await play_tracker.active_play(db, session.id)
    await engine.end_session_manually(db, session, active)
    await db.commit()
    return to_session_out(session)


@router.get("", response_model=Page[SessionOut])
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Literal["active", "completed", "hard_exit", "manual_exit"] | None = Query(
        None, alias="status"
    ),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Page[SessionOut]:
    rows, total = await session_service.list_sessions(db, user, page, page_size, status_filter)
    return Page[SessionOut](
        items=[to_session_out(s) for s in rows], total=total, page=page, page_size=page_size
    )
