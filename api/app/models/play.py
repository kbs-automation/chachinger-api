import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Uuid,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import P1_MODES, PLAY_STATUSES, RESULT_TYPES, Base, in_list, utcnow


class Play(Base):
    __tablename__ = "plays"
    __table_args__ = (
        CheckConstraint(in_list("p1_mode", P1_MODES, nullable=True), name="p1_mode_valid"),
        CheckConstraint(in_list("status", PLAY_STATUSES), name="status_valid"),
        CheckConstraint(in_list("result_type", RESULT_TYPES, nullable=True), name="result_valid"),
        CheckConstraint("play_number BETWEEN 1 AND 6", name="play_number_range"),
        CheckConstraint("click_cap > 0", name="click_cap_positive"),
        CheckConstraint("total_clicks >= 0 AND total_clicks <= click_cap", name="clicks_in_cap"),
        Index("ix_plays_session", "session_id", "cycle_number", "play_number"),
        Index(
            "uq_plays_one_active_per_session",
            "session_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("sessions.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    play_number: Mapped[int] = mapped_column(Integer, nullable=False)
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    p1_mode: Mapped[str | None] = mapped_column(String(30))
    p1_mode_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # INTERNAL — never exposed through any user-facing response schema.
    total_clicks: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    click_cap: Mapped[int] = mapped_column(Integer, nullable=False)
    confirmed_base: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    confirmed_press: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    confirmed_max: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    qualifying_result: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    result_type: Mapped[str | None] = mapped_column(String(20))
    win_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0"), server_default="0"
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
