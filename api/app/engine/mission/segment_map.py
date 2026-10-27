"""Central segment-id → click-range mapping (ES-040). Version with CONFIG_VERSION."""

from __future__ import annotations

# Tactical bands from WBA-010. Segment IDs that fall inside a band use that band.
# Numeric segment labels 1..N index these bands when the id is not a click-like value.
TACTICAL_BANDS: tuple[tuple[int, int], ...] = (
    (1, 6),
    (7, 13),
    (14, 19),
    (20, 29),
    (30, 39),
    (40, 49),
    (50, 59),
    (60, 69),
    (70, 96),
)

# Depth stages used by S11 / S12+ wager restrictions (click-based until sheet schema says otherwise).
S11_CLICK_START = 60
S12_CLICK_START = 70


def segment_to_clicks(segment_id: int) -> tuple[int, int]:
    """Map a source segment id to a click range. Does not invent clicks from weights."""
    if segment_id < 1:
        raise ValueError("segment_id must be >= 1")
    for start, end in TACTICAL_BANDS:
        if start <= segment_id <= end:
            return start, end
    if segment_id <= len(TACTICAL_BANDS):
        return TACTICAL_BANDS[segment_id - 1]
    # Unknown high id: single-click anchor (explicit mapping gap — keep narrow).
    return segment_id, segment_id


def band_for_click(click: int) -> tuple[int, int]:
    for start, end in TACTICAL_BANDS:
        if start <= click <= end:
            return start, end
    return (click, click)


def depth_stage(click: int) -> str:
    if click >= S12_CLICK_START:
        return "s12_plus"
    if click >= S11_CLICK_START:
        return "s11"
    return "normal"
