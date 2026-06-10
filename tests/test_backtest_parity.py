"""Live-path vs backtest parity: identical bars must produce identical trades."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

from goldsilver.data import backtest as backtest_mod
from goldsilver.data.models import GOLD, Bar
from goldsilver.data.models_macro import Signal
from goldsilver.data.settings import AppSettings
from goldsilver.data.trade_models import SimulatorSummary
from goldsilver.data.trades_service import TradesService


class _ScriptedMomentum:
    """Fires BUY on the 6th observation and SELL on the 11th — fully deterministic."""

    name = "Scripted Momentum"
    kind = "momentum"

    def __init__(self) -> None:
        self._count: dict[str, int] = {}

    def observe(self, symbol: str, price: float, at: datetime) -> Signal:
        i = self._count.get(symbol, 0)
        self._count[symbol] = i + 1
        action = "BUY" if i == 5 else ("SELL" if i == 10 else "NONE")
        return Signal(
            symbol=symbol,
            strategy=self.name,
            kind="momentum",
            action=action,
            intensity_sigma=1.0,
            reason="scripted",
            at=at,
        )

    def reset(self, symbol: str | None = None) -> None:
        self._count.clear()


class _SilentRecoil:
    name = "Silent Recoil"
    kind = "recoil"

    def observe(self, symbol: str, price: float, at: datetime) -> Signal:
        return Signal(
            symbol=symbol,
            strategy=self.name,
            kind="recoil",
            action="NONE",
            intensity_sigma=0.0,
            reason="scripted",
            at=at,
        )

    def reset(self, symbol: str | None = None) -> None:
        pass


def _bars() -> list[Bar]:
    # 12:00 UTC = 14:00 Stockholm — inside trading hours, all on one day.
    t0 = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    prices = [100.0 + 0.5 * i for i in range(15)]
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


def _trade_facts(summary: SimulatorSummary) -> list[tuple]:
    return [
        (t.side, t.units, t.price, t.ts_utc, t.reason, t.realized_pnl)
        for t in summary.recent_trades
    ]


async def _run_live_path(bars: list[Bar], settings: AppSettings) -> SimulatorSummary:
    sim = replace(settings.simulator, enabled=True, trigger_mode="either")
    svc = TradesService(sim, persist=False)
    mom = _ScriptedMomentum()
    rec = _SilentRecoil()
    for bar in bars:
        m = mom.observe(GOLD, bar.close, bar.time)
        r = rec.observe(GOLD, bar.close, bar.time)
        await svc.on_signal(
            symbol=GOLD,
            price=bar.close,
            ts_utc=bar.time,
            mom=m,
            rec=r,
            last_prices={GOLD: (bar.close, bar.time)},
        )
    return svc.summary({GOLD: (bars[-1].close, bars[-1].time)})


async def test_backtest_matches_live_path(monkeypatch: pytest.MonkeyPatch) -> None:
    bars = _bars()
    settings = AppSettings()
    monkeypatch.setattr(backtest_mod, "load_day", lambda _s, _d: bars)
    monkeypatch.setattr(
        backtest_mod, "STRATEGY_REGISTRY", (_ScriptedMomentum, _SilentRecoil)
    )

    bt = await backtest_mod.run_backtest(
        GOLD,
        date(2026, 6, 10),
        settings,
        momentum="Scripted Momentum",
        recoil="Silent Recoil",
        trigger_mode="either",
    )
    live = await _run_live_path(bars, settings)

    assert _trade_facts(bt) == _trade_facts(live)
    assert len(_trade_facts(bt)) == 2  # the scripted BUY and SELL actually executed
    assert bt.cash == live.cash
    assert bt.lifetime_realized_pnl == live.lifetime_realized_pnl
