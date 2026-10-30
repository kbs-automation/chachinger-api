"""Version stamps persisted with every mission-critical decision (DM-130/131)."""

# Bump when mission-critical code behavior changes (not pure config/parser).
ENGINE_VERSION = "0.3.0-tab11"

# Bump when Tab 12 CFG-* threshold bundle changes.
CONFIG_VERSION = "0.3.0"

# Bump when Enhanced Sheet parsing/normalization changes (Tab 13).
# 0.2.0: weighted tokens locked to Lookup segment-first (supersedes ES-031 weight-first).
# 0.3.0: token_format id + segment map without invented ranges; snapshot hydrate (no silent reparse).
PARSER_VERSION = "0.3.0"

# Wire format for weighted tokens (independent of source_schema_version / workbook id).
# Value matches the client's confirmed convention: segment*count.
# Old servers (extra=forbid, no this field) return 422 if the client sends token_format —
# so they cannot silently misread new-format tokens as weight-first.
TOKEN_FORMAT = "segment_count_v1"
SUPPORTED_TOKEN_FORMATS: frozenset[str] = frozenset({TOKEN_FORMAT})
