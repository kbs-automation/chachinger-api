from app.engine.zone_maps import PLAYS_PER_CYCLE
from app.models import GameSession, User
from app.schemas.auth import UserProfile
from app.schemas.sessions import SessionOut
from app.services import storage


def to_profile(user: User) -> UserProfile:
    return UserProfile(
        id=user.id,
        player_number=user.player_number,
        username=user.display_name,
        email=user.email,
        avatar_url=storage.avatar_url(user.avatar_url),
        tier=user.tier,
        subscription_status=user.subscription_status,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def current_play_number(session: GameSession) -> int:
    """Plays advance strictly 1..6 then wrap, so the count alone determines the position."""
    count = session.play_count or 0
    return ((count - 1) % PLAYS_PER_CYCLE) + 1 if count > 0 else 1


def to_session_out(session: GameSession) -> SessionOut:
    return SessionOut(
        id=session.id,
        p1_mode=session.p1_mode,
        status=session.status,
        session_budget=session.session_budget,
        current_balance=session.current_balance,
        total_wagered=session.total_wagered,
        confirmed_base=session.confirmed_base,
        confirmed_press=session.confirmed_press,
        confirmed_max=session.confirmed_max,
        play_count=session.play_count,
        play_number=current_play_number(session),
        cycle_number=session.cycle_number,
        execution_grade=session.execution_grade,
        started_at=session.started_at,
        ended_at=session.ended_at,
    )
