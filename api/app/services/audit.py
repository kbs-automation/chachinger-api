from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminAuditLog, User


async def record_admin_action(
    db: AsyncSession,
    admin: User,
    action: str,
    target_type: str | None,
    target_id: str | None,
    payload: dict[str, Any] | None,
    ip_address: str | None,
) -> AdminAuditLog:
    """Must run inside the same transaction as the write it describes (Rule 5).

    Flushing here surfaces any audit failure before the caller commits, so the
    caller's whole transaction rolls back with it.
    """
    entry = AdminAuditLog(
        admin_user_id=admin.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        payload=payload,
        ip_address=ip_address,
    )
    db.add(entry)
    await db.flush()
    return entry
