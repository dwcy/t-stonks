from __future__ import annotations

from marketcore.widgets.chart import (
    STALE_SLIDE_CAP_MIN,
    STALE_SLIDE_MIN,
    _live_window,
)

WINDOW = 24 * 60


def test_fresh_feed_pins_right_edge_to_last_bar() -> None:
    span = 600.0
    xmin, xmax = _live_window(span + STALE_SLIDE_MIN / 2, span, WINDOW)
    assert xmax == span
    assert xmin == max(0.0, span - WINDOW)


def test_brief_lag_slides_to_now() -> None:
    span = 600.0
    now_offset = span + 10.0
    xmin, xmax = _live_window(now_offset, span, WINDOW)
    assert xmax == now_offset


def test_weekend_gap_keeps_last_bars_visible() -> None:
    # Gap far beyond the cap (e.g. ~30h overnight/weekend) must not slide the
    # window past the data — the last bar stays at the right edge.
    span = float(WINDOW)
    now_offset = span + 1800.0
    xmin, xmax = _live_window(now_offset, span, WINDOW)
    assert xmax == span
    assert xmin <= span <= xmax


def test_gap_exactly_at_cap_still_slides() -> None:
    span = 600.0
    now_offset = span + STALE_SLIDE_CAP_MIN
    _, xmax = _live_window(now_offset, span, WINDOW)
    assert xmax == now_offset
