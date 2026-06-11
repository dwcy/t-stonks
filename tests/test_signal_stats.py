"""Tests for hit-rate scoring of strategy signals against forward prices."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from goldsilver.data.models import GOLD, Bar
from goldsilver.data.models_macro import Signal
from goldsilver.data.signal_stats import score_signals


class _Scripted:
    """BUY at index 5, SELL at index 20 — deterministic for scoring."""

    name = "Scripted"
    kind = "momentum"

    def __init__(self) -> None:
        self._i = -1

    def observe(self, symbol: str, price: float, at: datetime) -> Signal:
        self._i += 1
        action = "BUY" if self._i == 5 else ("SELL" if self._i == 20 else "NONE")
        return Signal(
            symbol=symbol,
            strategy=self.name,
            kind="momentum",
            action=action,
            intensity_sigma=1.0,
            reason="scripted",
            at=at,
        )


def _bars(prices: list[float]) -> list[Bar]:
    t0 = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    return [
        Bar(
            symbol=GOLD,
            time=t0 + timedelta(minutes=i),
            open=p,
            high=p,
            low=p,
            close=p,
            volume=0.0,
        )
        for i, p in enumerate(prices)
    ]


def test_buy_into_rise_wins_sell_into_rise_loses() -> None:
    bars = _bars([100.0 + 0.5 * i for i in range(40)])

    score = score_signals(bars, _Scripted(), GOLD, horizon=timedelta(minutes=10))

    assert score.fires == 2
    assert score.scored == 2
    assert score.wins == 1  # the BUY won, the SELL lost


def test_fire_without_forward_bar_is_not_scored() -> None:
    bars = _bars([100.0] * 22)  # SELL at i=20 has no bar 10m later

    score = score_signals(bars, _Scripted(), GOLD, horizon=timedelta(minutes=10))

    assert score.fires == 2
    assert score.scored == 1
