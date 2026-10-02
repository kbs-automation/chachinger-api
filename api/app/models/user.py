import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, Text, Uuid, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import SUBSCRIPTION_STATUSES, TIERS, Base, in_list, utcnow


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(in_list("tier", TIERS), name="tier_valid"),
        CheckConstraint(
            in_list("subscription_status", SUBSCRIPTION_STATUSES, nullable=True),
            name="subscription_status_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    player_number: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    # Null means the default display name "PLAYER"; a literal default would break UNIQUE.
    username: Mapped[str | None] = mapped_column(String(64), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Stores the S3 object key; presigned URLs are generated on read.
    avatar_url: Mapped[str | None] = mapped_column(Text)
    tier: Mapped[str] = mapped_column(
        String(20), nullable=False, default="vip", server_default="vip"
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    subscription_status: Mapped[str | None] = mapped_column(String(20))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )

    @property
    def display_name(self) -> str:
        return self.username or "PLAYER"
