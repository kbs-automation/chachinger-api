"""Weighted Band Authority — planned posture per region (Tab 02, CFG-161/162)."""

from __future__ import annotations

from app.engine.mission.config_rules import (
    NORMAL_MAX_MIN_CORROBORATORS,
    PRESS_MIN_CORROBORATORS,
    VALIDATED_DENSITY_PCT,
    VALIDATED_STRENGTH_MULT,
    WEAK_STRENGTH_MAX_MIN_CORROBORATORS,
)
from app.engine.mission.enums import WagerAuthority
from app.engine.mission.segment_map import depth_stage
from app.engine.mission.sheet import NormalizedSheet
from app.engine.mission.targets import Target, region_at


def corroborators(sheet: NormalizedSheet, target: Target) -> list[str]:
    items: list[str] = []
    if "row_19" in target.source_support:
        items.append("row_19")
    if "primary_density" in target.source_support or (
        sheet.primary_density.percent is not None and sheet.primary_density.percent > 0
    ):
        items.append("primary_density")
    if sheet.secondary_density.percent is not None and sheet.secondary_density.percent > 0:
        items.append("secondary_density")
    if sheet.row_4:
        items.append("row_4")
    if sheet.row_5:
        items.append("row_5")
    if "pocket" in target.source_support:
        items.append("pocket")
    # Unique preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def strength_validated(sheet: NormalizedSheet, prev_multiplier: float | None = None) -> bool:
    strength = (sheet.primary_density.strength or "").upper()
    if strength == "STRONG":
        return True
    if sheet.primary_density.percent is not None and sheet.primary_density.percent >= VALIDATED_DENSITY_PCT:
        return True
    if prev_multiplier is not None and prev_multiplier >= VALIDATED_STRENGTH_MULT:
        return True
    return False


def prior_strength_weak(prev_multiplier: float | None) -> bool:
    return prev_multiplier is None or prev_multiplier < VALIDATED_STRENGTH_MULT


def _press_eligible(sheet: NormalizedSheet, target: Target) -> bool:
    has_89 = "row_8_9" in target.source_support
    has_10 = "row_10" in target.source_support
    if has_89 and has_10:
        return True
    n = len(corroborators(sheet, target))
    if (has_89 or has_10) and n >= PRESS_MIN_CORROBORATORS:
        return True
    return False


def _cfg161_s11_max(
    sheet: NormalizedSheet,
    target: Target,
    *,
    kind: str,
    pcs_unstable: bool,
    prev_multiplier: float | None,
) -> bool:
    """CFG-161 all-required exceptional MAX checklist (TC-096/097)."""
    if kind == "bridge":
        return False
    if pcs_unstable:
        return False
    has_89 = "row_8_9" in target.source_support
    has_10 = "row_10" in target.source_support
    if not (has_89 and has_10):
        return False
    if len(corroborators(sheet, target)) < 2:
        return False
    if not strength_validated(sheet, prev_multiplier):
        return False
    return True


def _cfg162_s12_press(
    sheet: NormalizedSheet,
    target: Target,
    *,
    kind: str,
    pcs_unstable: bool,
    prev_multiplier: float | None,
) -> bool:
    """CFG-162 all-required S12+ PRESS checklist (TC-098/099). MAX stays disabled."""
    if kind == "bridge":
        return False
    if pcs_unstable:
        return False
    if "row_8_9" not in target.source_support:
        return False
    extra_core = "row_10" in target.source_support or "row_19" in target.source_support
    if not extra_core:
        return False
    if len(corroborators(sheet, target)) < 1:
        return False
    if not strength_validated(sheet, prev_multiplier):
        return False
    return True


def _normal_max(
    sheet: NormalizedSheet,
    target: Target,
    *,
    prev_multiplier: float | None,
) -> bool:
    has_89 = "row_8_9" in target.source_support
    has_10 = "row_10" in target.source_support
    if not (has_89 and has_10):
        return False
    needed = (
        WEAK_STRENGTH_MAX_MIN_CORROBORATORS
        if prior_strength_weak(prev_multiplier)
        else NORMAL_MAX_MIN_CORROBORATORS
    )
    if len(corroborators(sheet, target)) < needed:
        return False
    if prior_strength_weak(prev_multiplier) and not strength_validated(sheet, prev_multiplier):
        # LOCAL_MAX_OVERRIDE still needs two corroborators (already checked) + 8/9+10.
        return len(corroborators(sheet, target)) >= WEAK_STRENGTH_MAX_MIN_CORROBORATORS
    return True


def planned_authority(
    sheet: NormalizedSheet,
    click: int,
    targets: list[Target],
    bridges: list,
    *,
    input_quality: str,
    prev_multiplier: float | None = None,
    pcs_unstable: bool = False,
) -> tuple[WagerAuthority, str]:
    """Return planned band authority and a short reason code."""
    kind, target, _bridge = region_at(click, targets, bridges)

    if kind == "bridge":
        return "below_base", "bridge_survival"
    if kind == "none":
        return "below_base", "unsupported_space"
    if kind == "pre_entry":
        assert target is not None
        ceiling, _ = planned_authority(
            sheet,
            target.start_click,
            targets,
            bridges,
            input_quality=input_quality,
            prev_multiplier=prev_multiplier,
            pcs_unstable=pcs_unstable,
        )
        if ceiling in ("press", "max"):
            return "base", "pre_entry_rearm"
        return "below_base" if ceiling == "below_base" else "base", "pre_entry_rearm"

    assert target is not None
    if input_quality == "invalid":
        return "below_base", "invalid_input"

    stage = depth_stage(click)

    # Deep stages always use CFG-161/162 checklists (not the degraded PRESS shortcut).
    if stage == "s12_plus":
        if _cfg162_s12_press(
            sheet, target, kind=kind, pcs_unstable=pcs_unstable, prev_multiplier=prev_multiplier
        ):
            return "press", "cfg162_s12_press"
        return "base", "s12_deep_burn_base"

    if stage == "s11":
        if _cfg161_s11_max(
            sheet, target, kind=kind, pcs_unstable=pcs_unstable, prev_multiplier=prev_multiplier
        ):
            return "max", "cfg161_s11_max"
        if input_quality != "degraded" and _press_eligible(sheet, target):
            return "press", "s11_press"
        return "base", "s11_base"

    if input_quality == "degraded":
        if _press_eligible(sheet, target) and corroborators(sheet, target):
            return "press", "degraded_press"
        return "base", "degraded_base"

    if _normal_max(sheet, target, prev_multiplier=prev_multiplier):
        return "max", "qualified_max"
    if _press_eligible(sheet, target):
        return "press", "qualified_press"
    return "base", "supported_participation"
