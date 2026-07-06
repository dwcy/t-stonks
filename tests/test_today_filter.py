from __future__ import annotations

from datetime import datetime, timedelta, timezone

from goldsilver.app import _filter_to_stockholm_today
from goldsilver.data.models import Bar


def _bar(t: datetime) -> Bar:
    return Bar(symbol="XAU", time=t, open=1.0, high=1.0, low=1.0, close=1.0, volume=0.0)


def test_falls_back_to_last_session_when_today_empty() -> None:
    # All bars are days old, so the "today" window is empty — the chart must
    # still get the most recent session's bars instead of going blank.
    base = datetime.now(timezone.utc) - timedelta(days=3)
    bars = [_bar(base + timedelta(minutes=m)) for m in range(5)]
    bars += [_bar(base + timedelta(days=1, minutes=m)) for m in range(7)]

    result = _filter_to_stockholm_today(bars)

    assert len(result) == 7
    assert result[-1] is bars[-1]


def test_empty_input_returns_empty() -> None:
    assert _filter_to_stockholm_today([]) == []
