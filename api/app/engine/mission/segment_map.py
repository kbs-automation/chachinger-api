"""Central segment-id → click-range mapping (ES-040). Version with CONFIG_VERSION.

Lookup segment ordinals index TACTICAL_BANDS. Unmapped segment ids return None —
we never invent a synthetic (id, id) click range and we do not impose a hard
maximum of 33 or 97 on the identifier itself.
"""

from __future__ import annotations

# Tactical bands from WBA-010. Segment ordinal N maps to TACTICAL_BANDS[N - 1].
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

# Explicit map only — extend when the workbook adds more ordinals. No invented entries.
SEGMENT_CLICK_MAP: dict[int, tuple[int, int]] = {
    index: band for index, band in enumerate(TACTICAL_BANDS, start=1)
}

# Depth stages used by S11 / S12+ wager restrictions (click-based until sheet schema says otherwise).
S11_CLICK_START = 60
S12_CLICK_START = 70


def segment_to_clicks(segment_id: int) -> tuple[int, int] | None:
    """Map a known segment ordinal to its click range, or None if unmapped.

    Does not invent clicks from weights or from bare unmapped ids.
    """
    if segment_id < 1:
        return None
    return SEGMENT_CLICK_MAP.get(segment_id)


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
