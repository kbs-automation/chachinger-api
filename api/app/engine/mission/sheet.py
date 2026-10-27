"""Enhanced sheet normalization + quality gate (Tab 13)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from app.engine.mission.tokens import ClickRange, SegmentToken, parse_range_list, parse_segment_list
from app.engine.mission.versions import PARSER_VERSION

InputQuality = Literal["ready", "degraded", "invalid"]


@dataclass
class EnhancedSheetRaw:
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
    # Just-completed play (DM-010/011). Used for PPCM and as WR "current".
    prev_ending_click: int | None = None
    prev_multiplier: float | None = None
    # Play before last — required for CFG-160 Weak Recompression "PREV".
    prior_ending_click: int | None = None


@dataclass(frozen=True)
class DensityInfo:
    percent: float | None
    sample_n: int | None
    strength: str | None


@dataclass(frozen=True)
class NormalizedSheet:
    row_2: tuple[SegmentToken, ...]
    row_4: tuple[SegmentToken, ...]
    row_5: tuple[SegmentToken, ...]
    row_7: int | None
    row_8: tuple[SegmentToken, ...]
    row_9: tuple[SegmentToken, ...]
    row_10: tuple[SegmentToken, ...]
    row_17: int | None
    row_18: float | None
    row_19: tuple[ClickRange, ...]
    pockets: tuple[ClickRange, ...]
    primary_density: DensityInfo
    secondary_density: DensityInfo
    input_quality: InputQuality
    warnings: tuple[str, ...]
    conflicts: tuple[str, ...]
    parser_version: str
    source_schema_version: str
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        def tokens(items: tuple[SegmentToken, ...]) -> list[dict[str, Any]]:
            return [{"segment_id": t.segment_id, "weight": t.weight, "raw": t.raw} for t in items]

        def ranges(items: tuple[ClickRange, ...]) -> list[dict[str, Any]]:
            return [{"start": r.start, "end": r.end, "raw": r.raw} for r in items]

        return {
            "row_2": tokens(self.row_2),
            "row_4": tokens(self.row_4),
            "row_5": tokens(self.row_5),
            "row_7": self.row_7,
            "row_8": tokens(self.row_8),
            "row_9": tokens(self.row_9),
            "row_10": tokens(self.row_10),
            "row_17": self.row_17,
            "row_18": self.row_18,
            "row_19": ranges(self.row_19),
            "pockets": ranges(self.pockets),
            "primary_density": asdict(self.primary_density),
            "secondary_density": asdict(self.secondary_density),
            "input_quality": self.input_quality,
            "warnings": list(self.warnings),
            "conflicts": list(self.conflicts),
            "parser_version": self.parser_version,
            "source_schema_version": self.source_schema_version,
            "raw": self.raw,
        }


def _strength_label(raw: str | None) -> str | None:
    if raw is None or not str(raw).strip():
        return None
    label = str(raw).strip().upper()
    if label in {"STRONG", "WATCH", "SUPPORT", "OBSERVATION", "UNKNOWN"}:
        return label
    return "UNKNOWN"


def normalize_sheet(raw: EnhancedSheetRaw) -> NormalizedSheet:
    warnings: list[str] = []
    conflicts: list[str] = []

    row_8 = tuple(parse_segment_list(raw.row_8))
    row_9 = tuple(parse_segment_list(raw.row_9))
    row_10 = tuple(parse_segment_list(raw.row_10))
    row_4 = tuple(parse_segment_list(raw.row_4))
    row_5 = tuple(parse_segment_list(raw.row_5))
    row_2 = tuple(parse_segment_list(raw.row_2))
    row_19 = tuple(parse_range_list(raw.row_19))
    pockets = tuple(parse_range_list(raw.pockets))

    if raw.row_8 and len(row_8) < len([x for x in raw.row_8 if str(x).strip()]):
        warnings.append("row_8_partial_parse")
    if raw.row_9 and len(row_9) < len([x for x in raw.row_9 if str(x).strip()]):
        warnings.append("row_9_partial_parse")
    if raw.row_19 and len(row_19) < len([x for x in raw.row_19 if str(x).strip()]):
        warnings.append("row_19_malformed_ignored")

    if (
        raw.row_17 is not None
        and raw.prev_ending_click is not None
        and raw.row_17 != raw.prev_ending_click
    ):
        conflicts.append("row_17_prev_click_mismatch")

    has_core = bool(row_8 or row_9 or row_10)
    if conflicts:
        quality: InputQuality = "invalid"
    elif not has_core:
        quality = "invalid"
        warnings.append("missing_core_rows_8_9_10")
    elif not (row_8 or row_9) or not row_10:
        # One backbone family missing → degraded (may still continue conservatively).
        quality = "degraded"
        warnings.append("incomplete_core_corroboration")
    else:
        quality = "ready"

    primary = DensityInfo(
        percent=float(raw.primary_density_pct) if raw.primary_density_pct is not None else None,
        sample_n=raw.density_sample_n,
        strength=_strength_label(raw.density_strength),
    )
    secondary = DensityInfo(
        percent=float(raw.secondary_density_pct) if raw.secondary_density_pct is not None else None,
        sample_n=None,
        strength=None,
    )

    return NormalizedSheet(
        row_2=row_2,
        row_4=row_4,
        row_5=row_5,
        row_7=raw.row_7,
        row_8=row_8,
        row_9=row_9,
        row_10=row_10,
        row_17=raw.row_17,
        row_18=float(raw.row_18) if raw.row_18 is not None else None,
        row_19=row_19,
        pockets=pockets,
        primary_density=primary,
        secondary_density=secondary,
        input_quality=quality,
        warnings=tuple(warnings),
        conflicts=tuple(conflicts),
        parser_version=PARSER_VERSION,
        source_schema_version=raw.source_schema_version or "UNKNOWN",
        raw=asdict(raw),
    )
