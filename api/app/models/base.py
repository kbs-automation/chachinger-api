from datetime import UTC, datetime

from sqlalchemy import JSON, MetaData, String
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import DeclarativeBase

# SQLite variants exist only so the test suite can run without Postgres.
JSONType = JSONB().with_variant(JSON(), "sqlite")
InetType = INET().with_variant(String(45), "sqlite")

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

P1_MODES = ("entertainment", "entertainment_plus", "strike", "pursuit", "deep_run_pro")
TIERS = ("vip", "black", "elite", "diamond")
SUBSCRIPTION_STATUSES = ("active", "trialing", "past_due", "canceled")
SESSION_STATUSES = ("active", "completed", "hard_exit", "manual_exit")
PLAY_STATUSES = ("active", "completed", "hard_exit", "manual_exit")
RESULT_TYPES = ("multiplier", "bonus", "hard_exit", "manual_exit")
POSTURES = ("base", "press", "max", "early_attack")


def in_list(column: str, values: tuple[str, ...], nullable: bool = False) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    clause = f"{column} IN ({quoted})"
    return f"{column} IS NULL OR {clause}" if nullable else clause


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
