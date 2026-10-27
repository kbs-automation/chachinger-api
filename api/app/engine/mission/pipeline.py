"""P2+ mission pipeline (SA-120): sheet → protection → targets → continuation → WBA → safety."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.engine.mission.continuation import evaluate_continuation
from app.engine.mission.decision import MissionDecision, build_versions, new_decision_id, utc_now_iso
from app.engine.mission.enums import BridgeState, GuidanceKey, WagerAuthority
from app.engine.mission.protection import ProtectionState, evaluate_protection
from app.engine.mission.safety import SafetyState, apply_safety
from app.engine.mission.sheet import EnhancedSheetRaw, NormalizedSheet, normalize_sheet
from app.engine.mission.targets import (
    Bridge,
    Target,
    apply_click_progress,
    bridges_between,
    build_targets,
    region_at,
)
from app.engine.mission.wba import planned_authority


@dataclass
class RoutePlan:
    targets: list[Target]
    bridges: list[Bridge]
    sheet: NormalizedSheet
    opening_click: int
    planned_opening: WagerAuthority | None
    live_opening: WagerAuthority | None
    bridge_state: BridgeState
    safety_reason: str | None
    protection: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "targets": [t.to_dict() for t in self.targets],
            "bridges": [b.to_dict() for b in self.bridges],
            "sheet": self.sheet.to_dict(),
            "opening_click": self.opening_click,
            "planned_opening": self.planned_opening,
            "live_opening": self.live_opening,
            "bridge_state": self.bridge_state,
            "safety_reason": self.safety_reason,
            "protection": self.protection,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RoutePlan:
        targets = [
            Target(
                target_id=t["target_id"],
                start_click=t["start_click"],
                end_click=t["end_click"],
                target_type=t["target_type"],
                strength=t["strength"],
                source_support=tuple(t["source_support"]),
                status=t.get("status", "upcoming"),
                planned_band_authority=t.get("planned_band_authority"),
                live_final_authority=t.get("live_final_authority"),
            )
            for t in data.get("targets", [])
        ]
        bridges = [Bridge(b["start_click"], b["end_click"]) for b in data.get("bridges", [])]
        sheet = normalize_sheet(EnhancedSheetRaw(**_raw_from_sheet_dict(data.get("sheet") or {})))
        return cls(
            targets=targets,
            bridges=bridges,
            sheet=sheet,
            opening_click=int(data.get("opening_click") or 1),
            planned_opening=data.get("planned_opening"),
            live_opening=data.get("live_opening"),
            bridge_state=data.get("bridge_state") or "off",
            safety_reason=data.get("safety_reason"),
            protection=data.get("protection"),
        )


def _raw_from_sheet_dict(sheet: dict[str, Any]) -> dict[str, Any]:
    raw = sheet.get("raw") or {}
    if raw:
        return {k: v for k, v in raw.items() if v is not None}
    return {}


def _bridge_state_for(click: int, targets: list[Target], bridges: list[Bridge]) -> BridgeState:
    kind, _, _ = region_at(click, targets, bridges)
    if kind == "bridge":
        return "active"
    if kind == "pre_entry":
        return "pre_entry"
    return "off"


def _guidance_for_bridge(bridge_state: BridgeState, base: GuidanceKey) -> GuidanceKey:
    if bridge_state == "active":
        return "ui_005_bridge"
    if bridge_state == "pre_entry":
        return "ui_006_re_arm"
    return base


def run_pipeline(
    raw: EnhancedSheetRaw,
    *,
    safety: SafetyState | None = None,
    below_base_available: bool = False,
    legacy_route_id: str | None = None,
    opening_click: int = 1,
    current_click: int | None = None,
) -> tuple[MissionDecision, RoutePlan]:
    sheet = normalize_sheet(raw)
    targets = build_targets(sheet) if sheet.input_quality != "invalid" else []
    click = current_click if current_click is not None else opening_click
    if targets and current_click is not None:
        targets = apply_click_progress(targets, current_click)
    # Geographic bridges use the full target map (exhausted fronts still leave travel gaps).
    bridges = bridges_between(targets)

    # CFG-160: PREV = prior_ending_click, CURRENT = just-completed prev_ending_click.
    wr_prev = raw.prior_ending_click
    wr_current = raw.prev_ending_click if raw.prev_ending_click is not None else raw.row_17
    wr_mult = float(raw.prev_multiplier) if raw.prev_multiplier is not None else None
    protection = evaluate_protection(
        [t for t in targets if t.status != "exhausted"],
        prev_click=wr_prev,
        current_click=wr_current,
        current_mult=wr_mult,
    )

    safety = safety or SafetyState()
    cont = evaluate_continuation(
        targets,
        input_quality=sheet.input_quality,
        force_exit=safety.force_exit,
        protection=protection,
        current_click=click,
    )

    planned: WagerAuthority | None = None
    live: WagerAuthority | None = None
    safety_reason: str | None = None
    bridge_state: BridgeState = "off"
    notes: list[str] = [
        f"input_quality={sheet.input_quality}",
        f"targets={len([t for t in targets if t.status != 'exhausted'])}",
        f"bridges={len(bridges)}",
        f"wr={protection.weak_recompression}",
        f"dfr={protection.dfr_active}",
        f"her={protection.her_active}",
    ]
    notes.extend(f"warn:{w}" for w in sheet.warnings)
    notes.extend(f"conflict:{c}" for c in sheet.conflicts)

    if cont.final_action == "continue":
        planned, plan_reason = planned_authority(
            sheet,
            click,
            targets,
            bridges,
            input_quality=sheet.input_quality,
            prev_multiplier=raw.prev_multiplier,
            pcs_unstable=safety.pcs_unstable,
        )
        live, safety_reason, force_exit = apply_safety(planned, safety)
        notes.append(f"wba:{plan_reason}")
        if force_exit:
            cont = evaluate_continuation(
                targets, input_quality=sheet.input_quality, force_exit=True, protection=protection
            )
            planned, live = None, None
        else:
            if live == "below_base" and not below_base_available:
                notes.append("below_base_planned_without_amount_execute_base")
                live = "base"
            bridge_state = _bridge_state_for(click, targets, bridges)

    versions = build_versions()
    guidance = cont.guidance_key
    if cont.final_action == "continue":
        guidance = _guidance_for_bridge(bridge_state, guidance)
        if safety_reason == "containment":
            guidance = "ui_011_containment"
        elif safety_reason == "base_only":
            guidance = "ui_012_base_only"
        elif safety_reason in {
            "aggression_reduced",
            "press_suppression",
            "flip_on",
            "cdm",
            "tws",
            "safety_ceiling",
            "pcs_unstable",
        }:
            guidance = "ui_013_aggression_reduced"

    decision = MissionDecision(
        decision_id=new_decision_id(),
        source="mission_critical",
        continuation_authority=cont.continuation_authority,
        hard_exit_state=cont.hard_exit_state,
        final_action=cont.final_action,
        primary_action=cont.primary_action,
        guidance_key=guidance,
        planned_band_authority=planned,
        live_final_authority=live,
        bridge_state=bridge_state,
        exit_reason=cont.exit_reason or safety_reason,
        engine_version=versions.engine_version,
        config_version=versions.config_version,
        parser_version=sheet.parser_version,
        calculated_at=utc_now_iso(),
        legacy_route_id=legacy_route_id,
        input_quality=sheet.input_quality,
        notes=tuple(notes),
    )
    plan = RoutePlan(
        targets=targets,
        bridges=bridges,
        sheet=sheet,
        opening_click=opening_click,
        planned_opening=planned,
        live_opening=live,
        bridge_state=bridge_state,
        safety_reason=safety_reason,
        protection={
            "weak_recompression": protection.weak_recompression,
            "recompression_validated": protection.recompression_validated,
            "hidden_expansion_review": protection.hidden_expansion_review,
            "dfr_active": protection.dfr_active,
            "her_active": protection.her_active,
        },
    )
    return decision, plan


def authority_at_click(
    plan: RoutePlan,
    click: int,
    *,
    below_base_available: bool = False,
    safety: SafetyState | None = None,
) -> tuple[WagerAuthority, WagerAuthority, BridgeState]:
    targets = apply_click_progress(plan.targets, click)
    bridges = bridges_between(plan.targets)
    safety = safety or SafetyState()
    prev_mult = None
    raw = plan.sheet.raw or {}
    if raw.get("prev_multiplier") is not None:
        prev_mult = float(raw["prev_multiplier"])
    planned, _ = planned_authority(
        plan.sheet,
        click,
        targets,
        bridges,
        input_quality=plan.sheet.input_quality,
        prev_multiplier=prev_mult,
        pcs_unstable=safety.pcs_unstable,
    )
    live, _, force_exit = apply_safety(planned, safety)
    if force_exit:
        return planned, "below_base", _bridge_state_for(click, targets, bridges)
    if live is None:
        live = "below_base"
    if live == "below_base" and not below_base_available:
        live = "base"
    return planned, live, _bridge_state_for(click, targets, bridges)
