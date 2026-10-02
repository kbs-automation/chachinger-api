import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import POSTURES, Base, in_list, utcnow


class Spin(Base):
    __tablename__ = "spins"
    __table_args__ = (
        CheckConstraint(in_list("posture", POSTURES), name="posture_valid"),
        CheckConstraint("click_number > 0", name="click_positive"),
        # Also guards against double-submitted spins racing for the same click.
        UniqueConstraint("play_id", "click_number", name="uq_spins_play_click"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    play_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("plays.id"), nullable=False)
    # INTERNAL ONLY — never exposed through any user-facing response schema.
    click_number: Mapped[int] = mapped_column(Integer, nullable=False)
    posture: Mapped[str] = mapped_column(String(20), nullable=False)
    bet_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    result_input: Mapped[str | None] = mapped_column(String(20))
    is_qualifying: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    spun_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
