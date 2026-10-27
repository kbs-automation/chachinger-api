"""Enhanced Excel ingest contract (Tab 13) — client sends cell values; server normalizes."""

from app.schemas.common import RequestModel, ResponseModel
from app.schemas.decision import MissionDecisionOut


class EnhancedSheetRequest(RequestModel):
    row_2: list[str] | None = None
    row_4: list[str] | None = None
    row_5: list[str] | None = None
    row_7: int | None = None
    row_8: list[str] | None = None
    row_9: list[str] | None = None
    row_10: list[str] | None = None
    row_17: int | None = None
    row_18: float | int | None = None
    row_19: list[str] | None = None
    primary_density_pct: float | None = None
    secondary_density_pct: float | None = None
    density_sample_n: int | None = None
    density_strength: str | None = None
    pockets: list[str] | None = None
    source_schema_version: str | None = None
    # Just-completed play (for PPCM / WR current).
    prev_ending_click: int | None = None
    prev_multiplier: float | None = None
    # Play before last (CFG-160 WR previous depth).
    prior_ending_click: int | None = None


class EnhancedSheetResponse(ResponseModel):
    input_quality: str
    warnings: list[str]
    conflicts: list[str]
    parser_version: str
    decision: MissionDecisionOut | None = None
