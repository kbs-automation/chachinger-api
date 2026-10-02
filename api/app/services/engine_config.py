from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EngineConfig
from app.services.errors import DomainError

DEFAULTS: dict[str, Any] = {
    "maintenance_mode": False,
    "early_attack_enabled": False,
    "execution_grade_default": "A+",
}


def _validate(key: str, value: Any) -> Any:
    if key in ("maintenance_mode", "early_attack_enabled"):
        if not isinstance(value, bool):
            raise DomainError(422, "invalid_config_value", f"{key} must be a boolean")
        return value
    if key == "execution_grade_default":
        if not isinstance(value, str) or not 1 <= len(value) <= 4:
            raise DomainError(422, "invalid_config_value", f"{key} must be 1–4 characters")
        return value
    raise DomainError(422, "unknown_config_key", f"Unknown engine config key: {key}")


def validate_updates(values: dict[str, Any]) -> dict[str, Any]:
    if not values:
        raise DomainError(422, "empty_update", "No config values supplied")
    return {k: _validate(k, v) for k, v in values.items()}


async def get_all(db: AsyncSession) -> dict[str, Any]:
    rows = (await db.scalars(select(EngineConfig))).all()
    merged = dict(DEFAULTS)
    merged.update({r.key: r.value for r in rows if r.key in DEFAULTS})
    return merged


async def get_value(db: AsyncSession, key: str) -> Any:
    row = await db.get(EngineConfig, key)
    return row.value if row is not None else DEFAULTS[key]
