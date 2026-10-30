"""Real Lookup-sheet tokens: segment-first (segment * count)."""

from app.engine.mission.segment_map import segment_to_clicks
from app.engine.mission.tokens import parse_segment_list, parse_segment_token


def test_lookup_row_values_segment_first():
    # Copied from Lookup workbook cells (split on ';').
    row4 = parse_segment_list(["1*138", "2*95", "3*74", "4*64"])
    assert [(t.segment_id, t.weight) for t in row4] == [
        (1, 138),
        (2, 95),
        (3, 74),
        (4, 64),
    ]
    # Segment 1 is mapped; weight 138 is never treated as a segment/click.
    assert segment_to_clicks(1) == (1, 6)
    assert segment_to_clicks(138) is None

    row8 = parse_segment_list(["1*6", "4*7", "2*7", "11", "25", "3*3"])
    assert [(t.segment_id, t.weight) for t in row8] == [
        (1, 6),
        (4, 7),
        (2, 7),
        (11, 1),
        (25, 1),
        (3, 3),
    ]

    row10 = parse_segment_list(["2*7", "4*7"])
    assert [(t.segment_id, t.weight) for t in row10] == [(2, 7), (4, 7)]


def test_weighted_token_rule_segment_times_weight():
    token = parse_segment_token("2*8")
    assert token is not None
    assert (token.segment_id, token.weight) == (2, 8)
