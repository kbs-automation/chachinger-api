"""Segment*count token format, mapping, and historical snapshot protection."""

from app.engine.mission.pipeline import RoutePlan, run_pipeline
from app.engine.mission.segment_map import SEGMENT_CLICK_MAP, segment_to_clicks
from app.engine.mission.sheet import (
    EnhancedSheetRaw,
    can_reparse_snapshot,
    normalize_sheet,
    normalized_sheet_from_snapshot,
)
from app.engine.mission.targets import build_targets_with_warnings
from app.engine.mission.tokens import parse_segment_list, parse_segment_token
from app.engine.mission.versions import PARSER_VERSION, TOKEN_FORMAT
from app.schemas.sheet import EnhancedSheetRequest
from pydantic import ValidationError
import pytest

from app.core.config import get_settings
from tests.helpers import API, new_session, register


def test_segment_count_orientation_real_lookup():
    tokens = parse_segment_list(["1*138", "2*95", "3*74", "4*64"])
    assert [(t.segment_id, t.weight) for t in tokens] == [
        (1, 138),
        (2, 95),
        (3, 74),
        (4, 64),
    ]
    assert parse_segment_token("2*7") == parse_segment_list(["2*7"])[0]
    assert (parse_segment_token("2*7").segment_id, parse_segment_token("2*7").weight) == (2, 7)


def test_parser_and_token_format_constants():
    assert PARSER_VERSION == "0.3.0"
    assert TOKEN_FORMAT == "segment_count_v1"
    sheet = normalize_sheet(
        EnhancedSheetRaw(row_8=["2"], row_9=["2"], row_10=["2"], token_format=None)
    )
    assert sheet.token_format == TOKEN_FORMAT
    assert sheet.parser_version == PARSER_VERSION
    assert sheet.source_schema_version == "UNKNOWN"


def test_request_rejects_unknown_token_format():
    with pytest.raises(ValidationError):
        EnhancedSheetRequest(row_8=["2"], token_format="weight_first_v0")
    ok = EnhancedSheetRequest(row_8=["2"], token_format="segment_count_v1")
    assert ok.token_format == "segment_count_v1"
    omitted = EnhancedSheetRequest(row_8=["2"])
    assert omitted.token_format is None


def test_source_schema_version_independent_of_token_format():
    sheet = normalize_sheet(
        EnhancedSheetRaw(
            row_8=["2"],
            row_9=["2"],
            row_10=["2"],
            source_schema_version="WORKBOOK_2024",
            token_format="segment_count_v1",
        )
    )
    assert sheet.source_schema_version == "WORKBOOK_2024"
    assert sheet.token_format == "segment_count_v1"


def test_segment_map_no_invented_ranges_or_hard_caps():
    assert segment_to_clicks(1) == (1, 6)
    assert segment_to_clicks(2) == (7, 13)
    assert segment_to_clicks(9) == (70, 96)
    # Unmapped — no (id, id) invention; ids above map size or sparse ids are None.
    assert segment_to_clicks(10) is None
    assert segment_to_clicks(33) is None
    assert segment_to_clicks(97) is None
    assert segment_to_clicks(138) is None
    assert 33 not in SEGMENT_CLICK_MAP
    assert 97 not in SEGMENT_CLICK_MAP


def test_unmapped_segment_skipped_with_warning():
    sheet = normalize_sheet(
        EnhancedSheetRaw(row_8=["2", "138"], row_9=["2"], row_10=["2"])
    )
    targets, warnings = build_targets_with_warnings(sheet)
    assert any(w == "unmapped_segment_id:138" for w in warnings)
    assert all(t.start_click == 7 and t.end_click == 13 for t in targets)


def test_snapshot_hydrate_does_not_reparse_raw_strings():
    decision, plan = run_pipeline(
        EnhancedSheetRaw(
            row_8=["1*6", "2"],
            row_9=["2"],
            row_10=["2"],
            primary_density_pct=50,
            token_format="segment_count_v1",
        )
    )
    assert decision.parser_version == PARSER_VERSION
    blob = plan.to_dict()
    # Mutate raw strings to a weight-first-looking payload — hydrate must ignore them.
    blob["sheet"]["raw"] = {"row_8": ["6*1"], "row_9": ["2"], "row_10": ["2"]}
    restored = RoutePlan.from_dict(blob)
    assert [(t.segment_id, t.weight) for t in restored.sheet.row_8] == [
        (1, 6),
        (2, 1),
    ]
    assert restored.sheet.token_format == TOKEN_FORMAT


def test_can_reparse_blocks_weight_first_era_snapshots():
    assert can_reparse_snapshot({"parser_version": "0.1.1", "raw": {"row_8": ["1*138"]}}) is False
    assert (
        can_reparse_snapshot(
            {"parser_version": "0.2.0", "token_format": TOKEN_FORMAT, "raw": {"row_8": ["1*138"]}}
        )
        is True
    )
    assert (
        can_reparse_snapshot({"parser_version": "0.3.0", "token_format": TOKEN_FORMAT}) is True
    )
    # Normalized rows without going through raw parse.
    snap = {
        "row_8": [{"segment_id": 1, "weight": 138, "raw": "1*138"}],
        "row_9": [],
        "row_10": [],
        "parser_version": "0.1.1",
        "input_quality": "ready",
        "warnings": [],
        "conflicts": [],
        "primary_density": {},
        "secondary_density": {},
        "raw": {"row_8": ["1*138"]},
    }
    hydrated = normalized_sheet_from_snapshot(snap)
    assert hydrated is not None
    assert hydrated.row_8[0].segment_id == 1
    assert hydrated.row_8[0].weight == 138


async def test_enhanced_sheet_returns_token_format(client, monkeypatch):
    monkeypatch.setenv("MISSION_CRITICAL_ENGINE", "true")
    get_settings.cache_clear()
    try:
        headers = await register(client)
        session = await new_session(client, headers, "entertainment", 1000)
        sid = session["session_id"]
        # Client may omit token_format — server still segment-first and echoes id.
        res = await client.post(
            f"{API}/sessions/{sid}/enhanced-sheet",
            json={
                "row_8": ["2", "6"],
                "row_9": ["2", "6"],
                "row_10": ["2"],
                "primary_density_pct": 55,
                "density_strength": "STRONG",
                "source_schema_version": "UNKNOWN",
            },
            headers=headers,
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["parser_version"] == PARSER_VERSION
        assert body["token_format"] == TOKEN_FORMAT

        # Explicit format accepted.
        res2 = await client.post(
            f"{API}/sessions/{sid}/enhanced-sheet",
            json={
                "row_8": ["2"],
                "row_9": ["2"],
                "row_10": ["2"],
                "token_format": "segment_count_v1",
            },
            headers=headers,
        )
        assert res2.status_code == 200, res2.text
        assert res2.json()["token_format"] == "segment_count_v1"

        # Unknown format rejected (also what protects old servers via extra=forbid once field exists).
        bad = await client.post(
            f"{API}/sessions/{sid}/enhanced-sheet",
            json={
                "row_8": ["2"],
                "row_9": ["2"],
                "row_10": ["2"],
                "token_format": "weight_first_v0",
            },
            headers=headers,
        )
        assert bad.status_code == 422
    finally:
        monkeypatch.delenv("MISSION_CRITICAL_ENGINE", raising=False)
        get_settings.cache_clear()
