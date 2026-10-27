"""Qualified targets, clusters, and bridges from normalized sheet (Tabs 04, 10)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from app.engine.mission.config_rules import SMALL_GAP_MAX_CLICKS, SMALL_GAP_MIN_SIGNALS
from app.engine.mission.segment_map import segment_to_clicks
from app.engine.mission.sheet import NormalizedSheet

TargetType = Literal["front", "mid", "deep", "clustered", "isolated"]
TargetStatus = Literal["upcoming", "active", "exhausted"]
SourceFlag = Literal["row_8_9", "row_10", "row_19", "primary_density", "pocket", "row_4_5"]


@dataclass
class Target:
    target_id: str
    start_click: int
    end_click: int
    target_type: TargetType
    strength: int
    source_support: tuple[SourceFlag, ...]
    status: TargetStatus = "upcoming"
    planned_band_authority: str | None = None
    live_final_authority: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Bridge:
    start_click: int
    end_click: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _type_for_range(start: int, end: int) -> TargetType:
    mid = (start + end) / 2
    if mid <= 19:
        return "front"
    if mid <= 49:
        return "mid"
    return "deep"


def _add_weight(
    buckets: dict[tuple[int, int], dict[str, Any]],
    start: int,
    end: int,
    weight: int,
    source: SourceFlag,
) -> None:
    key = (start, end)
    entry = buckets.setdefault(
        key, {"start": start, "end": end, "strength": 0, "sources": set()}
    )
    entry["strength"] += weight
    entry["sources"].add(source)


def build_targets(sheet: NormalizedSheet) -> list[Target]:
    buckets: dict[tuple[int, int], dict[str, Any]] = {}
    for token in (*sheet.row_8, *sheet.row_9):
        start, end = segment_to_clicks(token.segment_id)
        _add_weight(buckets, start, end, token.weight, "row_8_9")
    for token in sheet.row_10:
        start, end = segment_to_clicks(token.segment_id)
        _add_weight(buckets, start, end, token.weight + 1, "row_10")
    for pocket in sheet.pockets:
        _add_weight(buckets, pocket.start, pocket.end, 1, "pocket")
    # Row 19 may support/narrow only — never create alone (ES-043 / TC-041).
    if buckets:
        for refine in sheet.row_19:
            for key, entry in list(buckets.items()):
                start, end = key
                if refine.end < start or refine.start > end:
                    continue
                narrowed = (max(start, refine.start), min(end, refine.end))
                if narrowed[0] <= narrowed[1]:
                    entry["start"], entry["end"] = narrowed
                    entry["sources"].add("row_19")

    if sheet.primary_density.percent is not None and sheet.primary_density.percent > 0:
        for entry in buckets.values():
            entry["sources"].add("primary_density")
            entry["strength"] += 1
    if sheet.row_4 or sheet.row_5:
        for entry in buckets.values():
            entry["sources"].add("row_4_5")

    merged = _merge_targets(
        sorted(buckets.values(), key=lambda e: (e["start"], e["end"])), sheet
    )
    targets: list[Target] = []
    for i, entry in enumerate(merged, start=1):
        sources = tuple(sorted(entry["sources"]))
        start, end = int(entry["start"]), int(entry["end"])
        target_type: TargetType = "clustered" if entry.get("merged") else _type_for_range(start, end)
        if target_type != "clustered" and len(merged) > 1:
            # Isolated when separated from neighbors by a bridge gap.
            target_type = "isolated" if target_type == "deep" else target_type
        targets.append(
            Target(
                target_id=f"T{i}",
                start_click=start,
                end_click=end,
                target_type=target_type,
                strength=int(entry["strength"]),
                source_support=sources,  # type: ignore[arg-type]
            )
        )
    return targets


def _gap_support_signals(
    sheet: NormalizedSheet, gap_start: int, gap_end: int, left: dict, right: dict
) -> list[str]:
    """Independent live signals that materially support merging a small gap (HE-022)."""
    signals: list[str] = []
    for refine in sheet.row_19:
        if refine.start <= gap_end and refine.end >= gap_start:
            signals.append("row_19")
            break
    for pocket in sheet.pockets:
        if pocket.start <= gap_end and pocket.end >= gap_start:
            signals.append("pocket")
            break
    if sheet.primary_density.percent is not None and sheet.primary_density.percent > 0:
        signals.append("primary_density")
    if sheet.secondary_density.percent is not None and sheet.secondary_density.percent > 0:
        signals.append("secondary_density")
    # Shared dual core support across both sides counts as structural glue.
    if "row_8_9" in left["sources"] and "row_8_9" in right["sources"]:
        if "row_10" in left["sources"] or "row_10" in right["sources"]:
            signals.append("shared_core")
    if sheet.row_4 and sheet.row_5:
        signals.append("rows_4_5")
    return signals


def _merge_targets(entries: list[dict[str, Any]], sheet: NormalizedSheet) -> list[dict[str, Any]]:
    if not entries:
        return []
    out: list[dict[str, Any]] = [dict(entries[0], sources=set(entries[0]["sources"]))]
    for entry in entries[1:]:
        prev = out[-1]
        # Overlap or touching → merge (HE-020/021 / TC-013).
        if entry["start"] <= prev["end"] + 1:
            prev["end"] = max(prev["end"], entry["end"])
            prev["strength"] += entry["strength"]
            prev["sources"] |= set(entry["sources"])
            prev["merged"] = True
            continue
        gap_start = prev["end"] + 1
        gap_end = entry["start"] - 1
        gap = gap_end - gap_start + 1
        # Small gap merges only with >=2 independent supporting signals (TC-014/015).
        if 1 <= gap <= SMALL_GAP_MAX_CLICKS:
            signals = _gap_support_signals(sheet, gap_start, gap_end, prev, entry)
            if len(set(signals)) >= SMALL_GAP_MIN_SIGNALS:
                prev["end"] = max(prev["end"], entry["end"])
                prev["strength"] += entry["strength"]
                prev["sources"] |= set(entry["sources"])
                prev["merged"] = True
                continue
        out.append(dict(entry, sources=set(entry["sources"])))
    return out


def bridges_between(targets: list[Target]) -> list[Bridge]:
    if len(targets) < 2:
        return []
    bridges: list[Bridge] = []
    ordered = sorted(targets, key=lambda t: t.start_click)
    for left, right in zip(ordered, ordered[1:], strict=False):
        if right.start_click > left.end_click + 1:
            bridges.append(Bridge(left.end_click + 1, right.start_click - 1))
    return bridges


def region_at(
    click: int, targets: list[Target], bridges: list[Bridge]
) -> tuple[str, Target | None, Bridge | None]:
    """Return region kind: target | bridge | pre_entry | none."""
    live = [t for t in targets if t.status != "exhausted"]
    for target in live:
        if target.start_click <= click <= target.end_click:
            return "target", target, None
    for bridge in bridges:
        if bridge.start_click <= click <= bridge.end_click:
            return "bridge", None, bridge
    for target in live:
        if target.start_click - 2 <= click < target.start_click:
            return "pre_entry", target, None
    return "none", None, None


def apply_click_progress(targets: list[Target], click: int) -> list[Target]:
    """Mark targets exhausted after their END_CLICK (HE-013 / TC-012 / TC-100)."""
    updated: list[Target] = []
    for t in targets:
        status = t.status
        if click > t.end_click:
            status = "exhausted"
        elif t.start_click <= click <= t.end_click:
            status = "active"
        elif click < t.start_click:
            status = "upcoming"
        updated.append(
            Target(
                target_id=t.target_id,
                start_click=t.start_click,
                end_click=t.end_click,
                target_type=t.target_type,
                strength=t.strength,
                source_support=t.source_support,
                status=status,
                planned_band_authority=t.planned_band_authority,
                live_final_authority=t.live_final_authority,
            )
        )
    return updated


def live_targets(targets: list[Target]) -> list[Target]:
    return [t for t in targets if t.status != "exhausted"]
