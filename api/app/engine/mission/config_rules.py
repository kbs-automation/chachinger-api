"""Locked CFG thresholds referenced by WBA / Weak Recompression (Tab 12, 23)."""

# CFG-160 — all four required (WR-001..004).
WR_PREV_MIN = 60
WR_CURRENT_MAX = 39
WR_DROP_MIN = 0.50
WR_MULT_MAX = 25.0  # exclusive: multiplier < 25x

# CFG-110 / 111 / 112
NORMAL_MAX_MIN_CORROBORATORS = 1
WEAK_STRENGTH_MAX_MIN_CORROBORATORS = 2
PRESS_MIN_CORROBORATORS = 1

# HE-022 / TC-014–015 — small unsupported gap stays bridge unless 2 signals support merge.
SMALL_GAP_MAX_CLICKS = 5
SMALL_GAP_MIN_SIGNALS = 2

# Strength validation helpers (WBA-040 examples).
VALIDATED_STRENGTH_MULT = 25.0
VALIDATED_DENSITY_PCT = 50.0
