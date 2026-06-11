"""Shared widget formatting helpers: age strings and the up/down color palette."""

from __future__ import annotations

UP_COLOR = "#7dff8c"
DOWN_COLOR = "#ff6b6b"
FLAT_COLOR = "#7a7a8a"
MUTED_COLOR = "#a0a0b0"


def format_age(seconds: int) -> str:
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        h, rem = divmod(seconds, 3600)
        m = rem // 60
        return f"{h}h" if m == 0 else f"{h}h {m}m"
    d, rem = divmod(seconds, 86400)
    h = rem // 3600
    return f"{d}d" if h == 0 else f"{d}d {h}h"
