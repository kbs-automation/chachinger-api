import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import P1_MODES, SESSION_STATUSES, Base, in_list, utcnow


class GameSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(in_list("p1_mode", P1_MODES), name="p1_mode_valid"),
        CheckConstraint(in_list("status", SESSION_STATUSES), name="status_valid"),
        CheckConstraint("session_budget >= 0", name="budget_non_negative"),
        Index("ix_sessions_user_started", "user_id", "started_at"),
        Index("ix_sessions_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    p1_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    session_budget: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # The budget the player asked for; session_budget is derived from it and the bets.
    player_budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    current_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    confirmed_base: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    confirmed_press: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    confirmed_max: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    play_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cycle_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    total_wagered: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default="0"
    )
    execution_grade: Mapped[str | None] = mapped_column(String(4))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
