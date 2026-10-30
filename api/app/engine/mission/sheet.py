"""Enhanced sheet normalization + quality gate (Tab 13)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from app.engine.mission.tokens import ClickRange, SegmentToken, parse_range_list, parse_segment_list
from app.engine.mission.versions import (
    PARSER_VERSION,
    SUPPORTED_TOKEN_FORMATS,
    TOKEN_FORMAT,
)

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
    # Workbook / source schema id only (ES-063). Not the token operand order.
    source_schema_version: str | None = None
    # Optional wire format for weighted tokens (segment*count). Omitted by older clients.
    token_format: str | None = None
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
    token_format: str
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
            "token_format": self.token_format,
            "raw": self.raw,
        }


def validate_token_format(token_format: str | None) -> str:
    """Resolve token_format. Unknown values are conflicts (never silently remapped)."""
    if token_format is None or not str(token_format).strip():
        return TOKEN_FORMAT
    value = str(token_format).strip()
    if value not in SUPPORTED_TOKEN_FORMATS:
        raise ValueError(f"unsupported_token_format:{value}")
    return value


def _strength_label(raw: str | None) -> str | None:
    if raw is None or not str(raw).strip():
        return None
    label = str(raw).strip().upper()
    if label in {"STRONG", "WATCH", "SUPPORT", "OBSERVATION", "UNKNOWN"}:
        return label
    return "UNKNOWN"


def _tokens_from_stored(items: Any) -> tuple[SegmentToken, ...]:
    """Hydrate already-normalized tokens — never re-parse raw strings here."""
    if not isinstance(items, list):
        return ()
    out: list[SegmentToken] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            segment_id = int(item["segment_id"])
            weight = int(item["weight"])
        except (KeyError, TypeError, ValueError):
            continue
        if segment_id < 1 or weight < 1:
            continue
        raw = str(item.get("raw") or f"{segment_id}*{weight}")
        out.append(SegmentToken(segment_id=segment_id, weight=weight, raw=raw))
    return tuple(out)


def _ranges_from_stored(items: Any) -> tuple[ClickRange, ...]:
    if not isinstance(items, list):
        return ()
    out: list[ClickRange] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            start = int(item["start"])
            end = int(item["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if start < 1 or end < 1 or end < start:
            continue
        raw = str(item.get("raw") or f"{start}-{end}")
        out.append(ClickRange(start=start, end=end, raw=raw))
    return tuple(out)


def _density_from_stored(data: Any) -> DensityInfo:
    if not isinstance(data, dict):
        return DensityInfo(percent=None, sample_n=None, strength=None)
    percent = data.get("percent")
    sample_n = data.get("sample_n")
    return DensityInfo(
        percent=float(percent) if percent is not None else None,
        sample_n=int(sample_n) if sample_n is not None else None,
        strength=_strength_label(data.get("strength")),
    )


def normalized_sheet_from_snapshot(data: dict[str, Any]) -> NormalizedSheet | None:
    """Rebuild a NormalizedSheet from a persisted snapshot without reparsing raw tokens.

    Returns None when the snapshot has no normalized token rows (caller must not
    invent a migration by re-parsing old raw strings).
    """
    if not isinstance(data, dict):
        return None
    # Prefer normalized rows; presence of row_8 as list-of-dicts marks a snapshot.
    row_8_raw = data.get("row_8")
    if not isinstance(row_8_raw, list):
        return None
    if row_8_raw and not isinstance(row_8_raw[0], dict):
        # Looks like raw string tokens still — refuse silent reparse.
        return None

    quality = data.get("input_quality") or "invalid"
    if quality not in {"ready", "degraded", "invalid"}:
        quality = "invalid"

    token_format = data.get("token_format") or TOKEN_FORMAT
    parser_version = str(data.get("parser_version") or PARSER_VERSION)
    source_schema = str(data.get("source_schema_version") or "UNKNOWN")

    return NormalizedSheet(
        row_2=_tokens_from_stored(data.get("row_2")),
        row_4=_tokens_from_stored(data.get("row_4")),
        row_5=_tokens_from_stored(data.get("row_5")),
        row_7=data.get("row_7"),
        row_8=_tokens_from_stored(data.get("row_8")),
        row_9=_tokens_from_stored(data.get("row_9")),
        row_10=_tokens_from_stored(data.get("row_10")),
        row_17=data.get("row_17"),
        row_18=float(data["row_18"]) if data.get("row_18") is not None else None,
        row_19=_ranges_from_stored(data.get("row_19")),
        pockets=_ranges_from_stored(data.get("pockets")),
        primary_density=_density_from_stored(data.get("primary_density")),
        secondary_density=_density_from_stored(data.get("secondary_density")),
        input_quality=quality,  # type: ignore[arg-type]
        warnings=tuple(data.get("warnings") or ()),
        conflicts=tuple(data.get("conflicts") or ()),
        parser_version=parser_version,
        source_schema_version=source_schema,
        token_format=str(token_format),
        raw=dict(data.get("raw") or {}),
    )


def can_reparse_snapshot(data: dict[str, Any] | None) -> bool:
    """Whether raw strings in a stored sheet may be parsed with the current parser.

    Weight-first era (parser 0.1.x without token_format) must not be silently
    re-interpreted as segment*count. Explicit migration required.
    """
    if not isinstance(data, dict):
        return True
    stored_format = data.get("token_format")
    if isinstance(data.get("raw"), dict):
        stored_format = stored_format or data["raw"].get("token_format")
    parser = str(data.get("parser_version") or "")
    if stored_format in SUPPORTED_TOKEN_FORMATS:
        return True
    if stored_format:
        return False
    # Pre-token_format snapshots: only allow reparse if already segment-first era.
    if parser.startswith("0.1"):
        return False
    if parser.startswith("0.2") or parser.startswith("0.3"):
        return True
    # Unknown / missing parser on a snapshot — refuse reparse of raw.
    if data.get("row_8") is not None or data.get("raw"):
        return False
    return True


def normalize_sheet(raw: EnhancedSheetRaw) -> NormalizedSheet:
    warnings: list[str] = []
    conflicts: list[str] = []

    try:
        token_format = validate_token_format(raw.token_format)
    except ValueError as exc:
        conflicts.append(str(exc))
        token_format = TOKEN_FORMAT

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
        token_format=token_format,
        raw=asdict(raw),
    )
