import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.common import Page
from app.engine import postures
from app.engine.mission.sheet import EnhancedSheetRaw
from app.engine.mission.versions import TOKEN_FORMAT
from app.schemas.routes import NextRouteResponse, RouteQuoteRequest, SelectRouteRequest
from app.schemas.sessions import (
    CreateSessionRequest,
    CreateSessionResponse,
    RecalculateBudgetRequest,
    RecalculateBudgetResponse,
    SessionOut,
)
from app.schemas.sheet import EnhancedSheetRequest, EnhancedSheetResponse
from app.serializers import to_next_route, to_session_out
from app.services import budget, engine, mission_decision, next_route, play_tracker
from app.services import sessions as session_service
from app.services.errors import DomainError

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
    result = await budget.recalculate_session_budget(
        db,
        session,
        body.base,
        body.press,
        body.max,
        body.chosen_postures,
        body.below_base,
    )
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


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def discard_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    session = await session_service.get_owned_session(db, user, session_id, for_update=True)
    await session_service.discard_unplayed_session(db, session)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{session_id}/enhanced-sheet", response_model=EnhancedSheetResponse)
async def submit_enhanced_sheet(
    session_id: uuid.UUID,
    body: EnhancedSheetRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EnhancedSheetResponse:
    """Ingest Enhanced Excel cell values and run the mission pipeline (points 4–5)."""
    if not mission_decision.enabled():
        raise DomainError(
            409,
            "mission_engine_disabled",
            "Enable MISSION_CRITICAL_ENGINE to submit Enhanced Sheet data",
        )
    session = await session_service.get_owned_session(db, user, session_id, for_update=True)
    raw = EnhancedSheetRaw(
        row_2=body.row_2,
        row_4=body.row_4,
        row_5=body.row_5,
        row_7=body.row_7,
        row_8=body.row_8,
        row_9=body.row_9,
        row_10=body.row_10,
        row_17=body.row_17,
        row_18=body.row_18,
        row_19=body.row_19,
        primary_density_pct=body.primary_density_pct,
        secondary_density_pct=body.secondary_density_pct,
        density_sample_n=body.density_sample_n,
        density_strength=body.density_strength,
        pockets=body.pockets,
        source_schema_version=body.source_schema_version,
        token_format=body.token_format,
        prev_ending_click=body.prev_ending_click,
        prev_multiplier=body.prev_multiplier,
        prior_ending_click=body.prior_ending_click,
    )
    decision = mission_decision.decide_from_sheet(
        session, raw, legacy_route_id=session.pending_route, persist=True
    )
    await db.commit()
    sheet = session.enhanced_sheet or {}
    return EnhancedSheetResponse(
        input_quality=str(sheet.get("input_quality") or decision.input_quality or "invalid"),
        warnings=list(sheet.get("warnings") or []),
        conflicts=list(sheet.get("conflicts") or []),
        parser_version=str(sheet.get("parser_version") or decision.parser_version),
        token_format=str(sheet.get("token_format") or TOKEN_FORMAT),
        decision=mission_decision.to_out(decision),
    )


@router.get("/{session_id}/next-route", response_model=NextRouteResponse)
async def get_next_route(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NextRouteResponse:
    session = await session_service.get_owned_session(db, user, session_id)
    return to_next_route(
        await next_route.describe(db, session), session, persist_decision=False
    )


@router.post("/{session_id}/next-route", response_model=NextRouteResponse)
async def choose_next_route(
    session_id: uuid.UUID,
    body: SelectRouteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NextRouteResponse:
    session = await session_service.get_owned_session(db, user, session_id, for_update=True)
    view = await next_route.select_route(db, session, body.route_id)
    response = to_next_route(view, session)
    await db.commit()
    return response


@router.post("/{session_id}/next-route/quote", response_model=NextRouteResponse)
async def quote_next_route(
    session_id: uuid.UUID,
    body: RouteQuoteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NextRouteResponse:
    session = await session_service.get_owned_session(db, user, session_id)
    active = (
        postures.chosen(body.active_postures, body.below_base)
        if body.base is not None or body.below_base is not None
        else None
    )
    return to_next_route(
        await next_route.describe(
            db,
            session,
            budget=body.budget,
            base=body.base,
            press=body.press,
            max_bet=body.max,
            active=active,
            below_base=body.below_base,
        ),
        session,
        persist_decision=False,
    )


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
