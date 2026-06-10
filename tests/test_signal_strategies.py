"""Regression tests for signal strategies: ZScoreRecoil must be able to fire."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from goldsilver.data.signal_strategies import ZScoreRecoil


def _run_series(strategy: ZScoreRecoil, prices: list[float]) -> list[str]:
    t0 = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    return [
        strategy.observe("XAU", price, t0 + timedelta(seconds=5 * i)).action
        for i, price in enumerate(prices)
    ]


def test_zscore_recoil_fires_buy_on_spike_down_then_recoil() -> None:
    strategy = ZScoreRecoil()
    strategy.set_param("z_threshold", 1.0)
    prices = [100.0] * 30 + [99.0, 97.5, 96.0, 95.0] + [98.0, 98.2, 98.4]

    actions = _run_series(strategy, prices)

    assert "BUY" in actions


def test_zscore_recoil_no_buy_while_histogram_still_falling() -> None:
    strategy = ZScoreRecoil()
    strategy.set_param("z_threshold", 1.0)
    prices = [100.0] * 30 + [99.0, 97.5, 96.0, 95.0]

    actions = _run_series(strategy, prices)

    assert "BUY" not in actions
