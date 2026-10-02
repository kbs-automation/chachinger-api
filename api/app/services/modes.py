from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import P1ModeConfig


async def list_active_modes(db: AsyncSession) -> list[P1ModeConfig]:
    return list(
        await db.scalars(
            select(P1ModeConfig)
            .where(P1ModeConfig.is_active.is_(True))
            .order_by(P1ModeConfig.sort_order)
        )
    )
