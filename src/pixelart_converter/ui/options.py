"""Output-option helpers used by the main window form (T4-2)."""

from __future__ import annotations

import re

from pixelart_converter.models import FrameItem, FrameRange, MultipleFrames

_FRAME_INDEX = re.compile(r"^\d+$")
_FRAME_RANGE = re.compile(r"^(\d+)\s*-\s*(\d+)$")


def parse_frame_list(text: str) -> MultipleFrames:
    """Parse a comma list of zero-based indices and inclusive ``start-end`` ranges."""

    items: list[FrameItem] = []
    for raw in text.split(","):
        token = raw.strip()
        if not token:
            continue
        range_match = _FRAME_RANGE.fullmatch(token)
        if range_match is not None:
            items.append(
                FrameRange(int(range_match.group(1)), int(range_match.group(2)))
            )
            continue
        if _FRAME_INDEX.fullmatch(token) is None:
            raise ValueError(f"invalid frame token: {token}")
        items.append(int(token))
    return MultipleFrames(tuple(items))
