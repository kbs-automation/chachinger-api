"""Enhanced Excel ingest contract (Tab 13) — client sends cell values; server normalizes."""

from pydantic import Field, field_validator

from app.engine.mission.versions import SUPPORTED_TOKEN_FORMATS, TOKEN_FORMAT
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
    # Workbook / source schema id only (ES-063). Never used as token operand order.
    source_schema_version: str | None = None
    # Optional. Confirmed client convention: segment*count → token_format=segment_count_v1.
    # Omitted on older clients (server still parses segment-first). When sent, unknown
    # values are rejected so old servers (extra=forbid) also 422 instead of silent misread.
    token_format: str | None = Field(default=None, max_length=64)
    # Just-completed play (for PPCM / WR current).
    prev_ending_click: int | None = None
    prev_multiplier: float | None = None
    # Play before last (CFG-160 WR previous depth).
    prior_ending_click: int | None = None

    @field_validator("token_format")
    @classmethod
    def _known_token_format(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            return None
        if text not in SUPPORTED_TOKEN_FORMATS:
            raise ValueError(
                f"unsupported token_format {text!r}; supported: {sorted(SUPPORTED_TOKEN_FORMATS)}"
            )
        return text


class EnhancedSheetResponse(ResponseModel):
    input_quality: str
    warnings: list[str]
    conflicts: list[str]
    parser_version: str
    token_format: str = TOKEN_FORMAT
    decision: MissionDecisionOut | None = None
