"""Canonical next-play decision object (Tabs 10, 15, 26)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.engine.mission.enums import (
    BridgeState,
    ContinuationAuthority,
    DecisionSource,
    FinalAction,
    GuidanceKey,
    HardExitState,
    PrimaryAction,
    WagerAuthority,
)
from app.engine.mission.versions import CONFIG_VERSION, ENGINE_VERSION, PARSER_VERSION


@dataclass(frozen=True)
class MissionVersions:
    engine_version: str
    config_version: str
    parser_version: str


def build_versions() -> MissionVersions:
    return MissionVersions(ENGINE_VERSION, CONFIG_VERSION, PARSER_VERSION)


@dataclass(frozen=True)
class MissionDecision:
    """Final Play Complete / next-play conclusion. Flutter binds to these fields only."""

    decision_id: str
    source: DecisionSource
    continuation_authority: ContinuationAuthority
    hard_exit_state: HardExitState
    final_action: FinalAction
    primary_action: PrimaryAction
    guidance_key: GuidanceKey
    planned_band_authority: WagerAuthority | None
    live_final_authority: WagerAuthority | None
    bridge_state: BridgeState
    exit_reason: str | None
    engine_version: str
    config_version: str
    parser_version: str
    calculated_at: str
    # Transitional: pocket route id while clients still select pockets.
    legacy_route_id: str | None = None
    input_quality: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def new_decision_id() -> str:
    return str(uuid4())


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
