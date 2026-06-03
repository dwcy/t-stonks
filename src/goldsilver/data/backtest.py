"""Replay a saved day through a throwaway simulator (no persistence)."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from goldsilver.data.history_store import load_day
from goldsilver.data.settings import AppSettings
from goldsilver.data.signal_strategies import STRATEGY_REGISTRY
from goldsilver.data.trade_models import SimulatorSummary
from goldsilver.data.trades_service import TradesService


async def run_backtest(
    symbol: str, day: date, settings: AppSettings
) -> SimulatorSummary:
    sim = replace(settings.simulator, enabled=True)
    svc = TradesService(sim, persist=False)

    bars = load_day(symbol, day)
    mom_cls = next(
        (c for c in STRATEGY_REGISTRY if c.name == settings.marker_momentum_strategy),
        None,
    )
    rec_cls = next(
        (c for c in STRATEGY_REGISTRY if c.name == settings.marker_recoil_strategy),
        None,
    )
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
