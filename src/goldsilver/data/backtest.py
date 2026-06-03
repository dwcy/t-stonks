"""Replay a saved day through a throwaway simulator (no persistence)."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from goldsilver.data.settings import AppSettings
from goldsilver.data.signal_strategies import STRATEGY_REGISTRY
from goldsilver.data.trade_models import SellMode, SimulatorSummary, TriggerMode
from goldsilver.data.history_store import load_day
from goldsilver.data.trades_service import TradesService


def _strategy(name: str):
    return next((c for c in STRATEGY_REGISTRY if c.name == name), None)


async def run_backtest(
    symbol: str,
    day: date,
    settings: AppSettings,
    *,
    momentum: str | None = None,
    recoil: str | None = None,
    sell_mode: SellMode | None = None,
    sell_pct: float | None = None,
    trigger_mode: TriggerMode | None = None,
    buy_pct: float | None = None,
) -> SimulatorSummary:
    sim = replace(
        settings.simulator,
        enabled=True,
        sell_mode=sell_mode if sell_mode is not None else settings.simulator.sell_mode,
        sell_pct=sell_pct if sell_pct is not None else settings.simulator.sell_pct,
        trigger_mode=(
            trigger_mode
            if trigger_mode is not None
            else settings.simulator.trigger_mode
        ),
        buy_pct=buy_pct if buy_pct is not None else settings.simulator.buy_pct,
    )
    svc = TradesService(sim, persist=False)

    bars = load_day(symbol, day)
    mom_cls = _strategy(momentum or settings.marker_momentum_strategy)
    rec_cls = _strategy(recoil or settings.marker_recoil_strategy)
    if not bars or mom_cls is None or rec_cls is None:
        return svc.summary({})

    mom = mom_cls()
    rec = rec_cls()
    for bar in bars:
        m = mom.observe(symbol, bar.close, bar.time)
        r = rec.observe(symbol, bar.close, bar.time)
        await svc.on_signal(
            symbol=symbol,
            price=bar.close,
            ts_utc=bar.time,
            mom=m,
            rec=r,
            last_prices={symbol: (bar.close, bar.time)},
        )

    last = bars[-1]
    return svc.summary({symbol: (last.close, last.time)})
