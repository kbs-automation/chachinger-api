"""Enhanced-sheet token parsing (ES-030/032 + Lookup orientation).

Weighted tokens are **segment-first**: `A*B` → segment_id=A, weight=B
(client convention `segment*count` / TOKEN_FORMAT segment_count_v1).
Tab 13 ES-031's weight-first wording is superseded.
Never treat weight as a click.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_WEIGHTED = re.compile(r"^\s*(\d+)\s*\*\s*(\d+)\s*$")
_PLAIN = re.compile(r"^\s*(\d+)\s*$")
_RANGE = re.compile(r"^\s*(\d+)\s*[-–:]\s*(\d+)\s*$")


@dataclass(frozen=True)
class SegmentToken:
    segment_id: int
    weight: int
    raw: str


@dataclass(frozen=True)
class ClickRange:
    start: int
    end: int
    raw: str


def parse_segment_token(raw: str) -> SegmentToken | None:
    text = str(raw).strip()
    if not text:
        return None
    weighted = _WEIGHTED.match(text)
    if weighted:
        # Lookup / client segment*count: left = segment_id, right = weight/count.
        segment_id = int(weighted.group(1))
        weight = int(weighted.group(2))
        if weight < 1 or segment_id < 1:
            return None
        return SegmentToken(segment_id=segment_id, weight=weight, raw=text)
    plain = _PLAIN.match(text)
    if plain:
        segment_id = int(plain.group(1))
        if segment_id < 1:
            return None
        return SegmentToken(segment_id=segment_id, weight=1, raw=text)
    return None


def parse_segment_list(values: list[str] | None) -> list[SegmentToken]:
    if not values:
        return []
    out: list[SegmentToken] = []
    for raw in values:
        token = parse_segment_token(raw)
        if token is not None:
            out.append(token)
    return out


def parse_range_token(raw: str) -> ClickRange | None:
    text = str(raw).strip()
    if not text:
        return None
    matched = _RANGE.match(text)
    if matched:
        start, end = int(matched.group(1)), int(matched.group(2))
        if start < 1 or end < 1 or end < start:
            return None
        return ClickRange(start=start, end=end, raw=text)
    plain = _PLAIN.match(text)
    if plain:
        click = int(plain.group(1))
        if click < 1:
            return None
        return ClickRange(start=click, end=click, raw=text)
    return None


def parse_range_list(values: list[str] | None) -> list[ClickRange]:
    if not values:
        return []
    out: list[ClickRange] = []
    for raw in values:
        item = parse_range_token(raw)
        if item is not None:
            out.append(item)
    return out
