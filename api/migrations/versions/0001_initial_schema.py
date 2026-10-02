"""Initial schema: users, sessions, plays, spins, p1_mode_configs, subscriptions_log,
admin_audit_log, engine_config. Seeds the five P1 mode configs.

Revision ID: 0001
Revises:
Create Date: 2026-10-01
"""
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.engine.zone_maps import MODE_SEEDS

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID_PK = dict(primary_key=True, server_default=sa.text("gen_random_uuid()"))
P1_MODES = "'entertainment', 'entertainment_plus', 'strike', 'pursuit', 'deep_run_pro'"
STATUSES = "'active', 'completed', 'hard_exit', 'manual_exit'"


def _ts(name: str, nullable: bool = True, default_now: bool = False) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=nullable,
        server_default=sa.text("now()") if default_now else None,
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), **UUID_PK),
        sa.Column("player_number", sa.String(10), nullable=False),
        sa.Column("username", sa.String(64)),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("avatar_url", sa.Text()),
        sa.Column("tier", sa.String(20), nullable=False, server_default="vip"),
        sa.Column("stripe_customer_id", sa.String(64)),
        sa.Column("subscription_status", sa.String(20)),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_flagged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_suspended", sa.Boolean(), nullable=False, server_default=sa.false()),
        _ts("last_login_at"),
        _ts("deleted_at"),
        _ts("created_at", nullable=False, default_now=True),
        _ts("updated_at", nullable=False, default_now=True),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("player_number", name="uq_users_player_number"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("stripe_customer_id", name="uq_users_stripe_customer_id"),
        sa.CheckConstraint(
            "tier IN ('vip', 'black', 'elite', 'diamond')", name="ck_users_tier_valid"
        ),
        sa.CheckConstraint(
            "subscription_status IS NULL OR subscription_status IN "
            "('active', 'trialing', 'past_due', 'canceled')",
            name="ck_users_subscription_status_valid",
        ),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), **UUID_PK),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("p1_mode", sa.String(30), nullable=False),
        sa.Column("session_budget", sa.Numeric(12, 2), nullable=False),
        sa.Column("current_balance", sa.Numeric(12, 2), nullable=False),
        sa.Column("confirmed_base", sa.Numeric(12, 2), nullable=False),
        sa.Column("confirmed_press", sa.Numeric(12, 2), nullable=False),
        sa.Column("confirmed_max", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("play_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cycle_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("total_wagered", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("execution_grade", sa.String(4)),
        _ts("started_at", nullable=False, default_now=True),
        _ts("ended_at"),
        sa.PrimaryKeyConstraint("id", name="pk_sessions"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_sessions_user_id_users"),
        sa.CheckConstraint(f"p1_mode IN ({P1_MODES})", name="ck_sessions_p1_mode_valid"),
        sa.CheckConstraint(f"status IN ({STATUSES})", name="ck_sessions_status_valid"),
        sa.CheckConstraint("session_budget >= 0", name="ck_sessions_budget_non_negative"),
    )
    op.create_index("ix_sessions_user_started", "sessions", ["user_id", "started_at"])
    op.create_index("ix_sessions_status", "sessions", ["status"])

    op.create_table(
        "plays",
        sa.Column("id", sa.Uuid(), **UUID_PK),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("play_number", sa.Integer(), nullable=False),
        sa.Column("cycle_number", sa.Integer(), nullable=False),
        sa.Column("p1_mode", sa.String(30)),
        sa.Column("p1_mode_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("total_clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("click_cap", sa.Integer(), nullable=False),
        sa.Column("confirmed_base", sa.Numeric(12, 2), nullable=False),
        sa.Column("confirmed_press", sa.Numeric(12, 2), nullable=False),
        sa.Column("confirmed_max", sa.Numeric(12, 2), nullable=False),
        sa.Column("qualifying_result", sa.Numeric(8, 2)),
        sa.Column("result_type", sa.String(20)),
        sa.Column("win_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False),
        _ts("started_at", nullable=False, default_now=True),
        _ts("ended_at"),
        sa.PrimaryKeyConstraint("id", name="pk_plays"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], name="fk_plays_session_id_sessions"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_plays_user_id_users"),
        sa.CheckConstraint(
            f"p1_mode IS NULL OR p1_mode IN ({P1_MODES})", name="ck_plays_p1_mode_valid"
        ),
        sa.CheckConstraint(f"status IN ({STATUSES})", name="ck_plays_status_valid"),
        sa.CheckConstraint(
            "result_type IS NULL OR result_type IN "
            "('multiplier', 'bonus', 'hard_exit', 'manual_exit')",
            name="ck_plays_result_valid",
        ),
        sa.CheckConstraint("play_number BETWEEN 1 AND 6", name="ck_plays_play_number_range"),
        sa.CheckConstraint("click_cap > 0", name="ck_plays_click_cap_positive"),
        sa.CheckConstraint(
            "total_clicks >= 0 AND total_clicks <= click_cap", name="ck_plays_clicks_in_cap"
        ),
    )
    op.create_index("ix_plays_session", "plays", ["session_id", "cycle_number", "play_number"])
    op.create_index(
        "uq_plays_one_active_per_session",
        "plays",
        ["session_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "spins",
        sa.Column("id", sa.Uuid(), **UUID_PK),
        sa.Column("play_id", sa.Uuid(), nullable=False),
        sa.Column("click_number", sa.Integer(), nullable=False),
        sa.Column("posture", sa.String(20), nullable=False),
        sa.Column("bet_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("result_input", sa.String(20)),
        sa.Column("is_qualifying", sa.Boolean(), nullable=False, server_default=sa.false()),
        _ts("spun_at", nullable=False, default_now=True),
        sa.PrimaryKeyConstraint("id", name="pk_spins"),
        sa.ForeignKeyConstraint(["play_id"], ["plays.id"], name="fk_spins_play_id_plays"),
        sa.UniqueConstraint("play_id", "click_number", name="uq_spins_play_click"),
        sa.CheckConstraint(
            "posture IN ('base', 'press', 'max', 'early_attack')", name="ck_spins_posture_valid"
        ),
        sa.CheckConstraint("click_number > 0", name="ck_spins_click_positive"),
    )

    p1_mode_configs = op.create_table(
        "p1_mode_configs",
        sa.Column("mode_id", sa.String(30), nullable=False),
        sa.Column("label", sa.String(64), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("click_cap", sa.Integer(), nullable=False),
        sa.Column("min_budget", sa.Numeric(12, 2)),
        sa.Column("baseline_base", sa.Numeric(12, 2)),
        sa.Column("baseline_press", sa.Numeric(12, 2)),
        sa.Column("baseline_max", sa.Numeric(12, 2)),
        sa.Column("zone_map", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("mode_id", name="pk_p1_mode_configs"),
        sa.CheckConstraint(f"mode_id IN ({P1_MODES})", name="ck_p1_mode_configs_mode_id_valid"),
        sa.CheckConstraint("click_cap > 0", name="ck_p1_mode_configs_click_cap_positive"),
    )

    op.create_table(
        "subscriptions_log",
        sa.Column("id", sa.Uuid(), **UUID_PK),
        sa.Column("user_id", sa.Uuid()),
        sa.Column("stripe_event_id", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("old_tier", sa.String(20)),
        sa.Column("new_tier", sa.String(20)),
        sa.Column("amount_cents", sa.Integer()),
        _ts("created_at", nullable=False, default_now=True),
        sa.PrimaryKeyConstraint("id", name="pk_subscriptions_log"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_subscriptions_log_user_id_users"
        ),
        sa.UniqueConstraint("stripe_event_id", name="uq_subscriptions_log_stripe_event_id"),
    )

    op.create_table(
        "admin_audit_log",
        sa.Column("id", sa.Uuid(), **UUID_PK),
        sa.Column("admin_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(32)),
        sa.Column("target_id", sa.String(64)),
        sa.Column("payload", postgresql.JSONB()),
        sa.Column("ip_address", postgresql.INET()),
        _ts("created_at", nullable=False, default_now=True),
        sa.PrimaryKeyConstraint("id", name="pk_admin_audit_log"),
        sa.ForeignKeyConstraint(
            ["admin_user_id"], ["users.id"], name="fk_admin_audit_log_admin_user_id_users"
        ),
    )
    op.create_index("ix_admin_audit_log_created", "admin_audit_log", ["created_at"])
    op.execute(
        """
        CREATE OR REPLACE FUNCTION admin_audit_log_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'admin_audit_log is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER admin_audit_log_no_mutation
        BEFORE UPDATE OR DELETE ON admin_audit_log
        FOR EACH ROW EXECUTE FUNCTION admin_audit_log_append_only();
        """
    )

    op.create_table(
        "engine_config",
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("updated_by", sa.Uuid()),
        _ts("updated_at", nullable=False, default_now=True),
        sa.PrimaryKeyConstraint("key", name="pk_engine_config"),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name="fk_engine_config_updated_by_users"
        ),
    )

    # Explicit CAST from JSON text keeps the seed working in both online and `--sql` offline mode.
    for seed in MODE_SEEDS:
        zone_map = sa.cast(sa.literal(json.dumps(seed["zone_map"]), sa.Text()), postgresql.JSONB)
        op.execute(p1_mode_configs.insert().values(**{**seed, "zone_map": zone_map}))


def downgrade() -> None:
    op.drop_table("engine_config")
    op.execute("DROP TRIGGER IF EXISTS admin_audit_log_no_mutation ON admin_audit_log")
    op.execute("DROP FUNCTION IF EXISTS admin_audit_log_append_only()")
    op.drop_index("ix_admin_audit_log_created", table_name="admin_audit_log")
    op.drop_table("admin_audit_log")
    op.drop_table("subscriptions_log")
    op.drop_table("p1_mode_configs")
    op.drop_table("spins")
    op.drop_index("uq_plays_one_active_per_session", table_name="plays")
    op.drop_index("ix_plays_session", table_name="plays")
    op.drop_table("plays")
    op.drop_index("ix_sessions_status", table_name="sessions")
    op.drop_index("ix_sessions_user_started", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
