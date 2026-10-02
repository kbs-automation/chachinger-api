from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Integer, Numeric, String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import P1_MODES, Base, JSONType, in_list


class P1ModeConfig(Base):
    __tablename__ = "p1_mode_configs"
    __table_args__ = (
        CheckConstraint(in_list("mode_id", P1_MODES), name="mode_id_valid"),
        CheckConstraint("click_cap > 0", name="click_cap_positive"),
    )

    mode_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    click_cap: Mapped[int] = mapped_column(Integer, nullable=False)
    min_budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    baseline_base: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    baseline_press: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    baseline_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    # CONFIDENTIAL — full 96-click [{s, e, t}] array. Never serialized to any client.
    zone_map: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
