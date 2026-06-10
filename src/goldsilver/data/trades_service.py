"""Trade simulator engine and JSON persistence."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timezone
from typing import Any

from goldsilver.data.models_macro import Signal
from goldsilver.data.settings import SimulatorSettings, trades_path
from goldsilver.data.trades_store import load_trades, save_trades
from goldsilver.data.trade_models import (
    ConsensusAction,
    DailyPnL,
    DayHistory,
    Position,
    PositionSnapshot,
    SimulatorState,
    SimulatorSummary,
    Trade,
    TradeReason,
)
from goldsilver.data.trading_hours import is_open, to_local

SettingsPersister = Callable[[], Awaitable[None] | None]
EnableChangedCallback = Callable[[], Awaitable[None] | None]

_MIN_BUY_USD = 1.0
_TRADE_CAP = 5000


class TradesService:
    def __init__(
        self,
        settings: SimulatorSettings,
        *,
        settings_persister: SettingsPersister | None = None,
        on_enable_changed: EnableChangedCallback | None = None,
        persist: bool = True,
    ) -> None:
        self._settings = settings
        self._settings_persister = settings_persister
        self._on_enable_changed = on_enable_changed
        self._persist_enabled = persist
        self._state = SimulatorState(cash=settings.initial_deposit)
        self._trades: list[Trade] = []
        self._daily: list[DailyPnL] = []
        self._lock = asyncio.Lock()
        if persist:
            self._load()

    async def on_signal(
        self,
        *,
        symbol: str,
        price: float,
        ts_utc: datetime,
        mom: Signal | None,
        rec: Signal | None,
        last_prices: dict[str, tuple[float, datetime]],
    ) -> None:
        async with self._lock:
            seen = self._state.last_processed_ts.get(symbol)
            if seen is not None and ts_utc <= seen:
                return
            now_local = to_local(ts_utc)
            self._check_clock(now_local, last_prices)
            consensus = self._consensus_action(mom, rec)
            prev = self._state.last_consensus_action.get(symbol, "NONE")
            self._state.last_consensus_action[symbol] = consensus
            if is_open(now_local) and consensus != "NONE" and prev != consensus:
                rule_snap = self._rule_snapshot()
                sig_snap = {
                    "momentum": mom.action if mom is not None else "NONE",
                    "recoil": rec.action if rec is not None else "NONE",
                    "momentum_strategy": mom.strategy if mom is not None else "",
                    "recoil_strategy": rec.strategy if rec is not None else "",
                }
                trade: Trade | None
                if consensus == "BUY":
                    trade = self._execute_buy(
                        symbol, price, ts_utc, rule_snap, sig_snap
                    )
                else:
                    trade = self._execute_sell(
                        symbol, price, ts_utc, "signal_sell", rule_snap, sig_snap
                    )
                if trade is not None:
                    self._trades.append(trade)
            self._state.last_processed_ts[symbol] = ts_utc
            if self._persist_enabled:
                await asyncio.to_thread(self._persist)

    async def liquidate_now(
        self, last_prices: dict[str, tuple[float, datetime]]
    ) -> None:
        async with self._lock:
            now_local = to_local(datetime.now(timezone.utc))
            self._liquidate_positions(now_local, last_prices, forced=True)
            await asyncio.to_thread(self._persist)

    async def reset_budget(self) -> None:
        async with self._lock:
            self._state = SimulatorState(cash=self._settings.initial_deposit)
            self._trades.clear()
            self._daily.clear()
            await asyncio.to_thread(self._persist)

    def summary(
        self,
        last_prices: dict[str, tuple[float, datetime]] | None = None,
    ) -> SimulatorSummary:
        prices = last_prices or {}
        now_local = to_local(datetime.now(timezone.utc))
        positions_snap: list[PositionSnapshot] = []
        for symbol, pos in self._state.positions.items():
            if pos.units <= 0.0:
                continue
            price_info = prices.get(symbol)
            last_p = price_info[0] if price_info is not None else pos.avg_cost
            mv = pos.units * last_p
            unr = mv - pos.cost_basis
            unr_pct = (unr / pos.cost_basis * 100.0) if pos.cost_basis > 0 else 0.0
            positions_snap.append(
                PositionSnapshot(
                    symbol, pos.units, pos.avg_cost, last_p, mv, unr, unr_pct
                )
            )
        init = self._settings.initial_deposit
        today_pct = (self._state.today_realized_pnl / init * 100.0) if init > 0 else 0.0
        lifetime_pct = (
            (self._state.lifetime_realized_pnl / init * 100.0) if init > 0 else 0.0
        )
        max_drawdown, win_rate, avg_win, avg_loss = self._trade_stats(init)
        return SimulatorSummary(
            enabled=self._settings.enabled,
            is_open=is_open(now_local),
            cash=self._state.cash,
            initial_deposit=init,
            today_realized_pnl=self._state.today_realized_pnl,
            lifetime_realized_pnl=self._state.lifetime_realized_pnl,
            today_pct=today_pct,
            lifetime_pct=lifetime_pct,
            positions=tuple(positions_snap),
            recent_trades=tuple(self._trades[-50:]),
            history=self._build_history(),
            sell_mode=self._settings.sell_mode,
            sell_pct=self._settings.sell_pct,
            trigger_mode=self._settings.trigger_mode,
            liquidated_for_day=self._state.liquidated_for_day,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
        )

    def _trade_stats(
        self, initial_deposit: float
    ) -> tuple[float, float | None, float | None, float | None]:
        wins: list[float] = []
        losses: list[float] = []
        equity = initial_deposit
        peak = initial_deposit
        max_drawdown = 0.0
        for t in self._trades:
            if t.side != "SELL":
                continue
            if t.realized_pnl > 0:
                wins.append(t.realized_pnl)
            elif t.realized_pnl < 0:
                losses.append(t.realized_pnl)
            equity += t.realized_pnl
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)
        closed = len(wins) + len(losses)
        win_rate = (len(wins) / closed * 100.0) if closed else None
        avg_win = (sum(wins) / len(wins)) if wins else None
        avg_loss = (sum(losses) / len(losses)) if losses else None
        return max_drawdown, win_rate, avg_win, avg_loss

    def _build_history(self) -> tuple[DayHistory, ...]:
        buys: dict[date, int] = {}
        sells: dict[date, int] = {}
        for t in self._trades:
            day = to_local(t.ts_utc).date()
            if t.side == "BUY":
                buys[day] = buys.get(day, 0) + 1
            else:
                sells[day] = sells.get(day, 0) + 1
        pnl_by_day: dict[date, float] = {d.day: d.realized_pnl for d in self._daily}
        days = set(buys) | set(sells) | set(pnl_by_day)
        rows = [
            DayHistory(
                day=d,
                buys=buys.get(d, 0),
                sells=sells.get(d, 0),
                realized_pnl=pnl_by_day.get(d, 0.0),
            )
            for d in sorted(days)
        ]
        return tuple(rows)

    async def update_settings(self, **changes: Any) -> None:
        async with self._lock:
            trigger_changed = (
                "trigger_mode" in changes
                and changes["trigger_mode"] != self._settings.trigger_mode
            )
            was_enabled = self._settings.enabled
            for k, v in changes.items():
                if hasattr(self._settings, k):
                    setattr(self._settings, k, v)
            self._settings.__post_init__()
            if trigger_changed:
                self._state.last_consensus_action.clear()
            now_enabled = self._settings.enabled
        if self._settings_persister is not None:
            result = self._settings_persister()
            if asyncio.iscoroutine(result):
                await result
        if now_enabled and not was_enabled and self._on_enable_changed is not None:
            result = self._on_enable_changed()
            if asyncio.iscoroutine(result):
                await result

    @property
    def settings(self) -> SimulatorSettings:
        return self._settings

    def _consensus_action(
        self, mom: Signal | None, rec: Signal | None
    ) -> ConsensusAction:
        a_mom = mom.action if mom is not None else "NONE"
        a_rec = rec.action if rec is not None else "NONE"
        if self._settings.trigger_mode == "both":
            if a_mom == "BUY" and a_rec == "BUY":
                return "BUY"
            if a_mom == "SELL" and a_rec == "SELL":
                return "SELL"
            return "NONE"
        actions = {a_mom, a_rec}
        if "BUY" in actions and "SELL" in actions:
            return "NONE"
        if "BUY" in actions:
            return "BUY"
        if "SELL" in actions:
            return "SELL"
        return "NONE"

    def _check_clock(
        self,
        now_local: datetime,
        last_prices: dict[str, tuple[float, datetime]],
    ) -> None:
        today = now_local.date()
        if self._state.day_start_local is None:
            self._state.day_start_local = today
        elif today != self._state.day_start_local:
            self._daily.append(
                DailyPnL(
                    day=self._state.day_start_local,
                    realized_pnl=self._state.today_realized_pnl,
                    end_cash=self._state.cash,
                )
            )
            self._state.today_realized_pnl = 0.0
            self._state.day_start_local = today
            self._state.liquidated_for_day = False
        if not is_open(now_local) and not self._state.liquidated_for_day:
            self._liquidate_positions(now_local, last_prices, forced=False)
            self._state.liquidated_for_day = True

    def _liquidate_positions(
        self,
        now_local: datetime,
        last_prices: dict[str, tuple[float, datetime]],
        *,
        forced: bool,
    ) -> None:
        ts_utc = now_local.astimezone(timezone.utc)
        rule_snap = self._rule_snapshot()
        for symbol, pos in list(self._state.positions.items()):
            if pos.units <= 0.0:
                continue
            price_info = last_prices.get(symbol)
            if price_info is None:
                continue
            price = price_info[0]
            trade = self._execute_sell_units(
                symbol=symbol,
                units=pos.units,
                price=price,
                ts_utc=ts_utc,
                reason="eod_liquidation",
                rule_snap=rule_snap,
                signals={"forced": "true" if forced else "false"},
            )
            if trade is not None:
                self._trades.append(trade)

    def _execute_buy(
        self,
        symbol: str,
        price: float,
        ts_utc: datetime,
        rule_snap: dict[str, object],
        sig_snap: dict[str, str],
    ) -> Trade | None:
        if price <= 0.0:
            return None
        spend = self._state.cash * self._settings.buy_pct
        if spend < _MIN_BUY_USD:
            return None
        units = spend / price
        cost = units * price
        pos = self._state.positions.get(symbol) or Position(symbol=symbol)
        new_units = pos.units + units
        new_cost_basis = pos.cost_basis + cost
        pos.avg_cost = new_cost_basis / new_units if new_units > 0 else 0.0
        pos.units = new_units
        self._state.positions[symbol] = pos
        self._state.cash -= cost
        return Trade(
            trade_id=str(uuid.uuid4()),
            ts_utc=ts_utc,
            symbol=symbol,
            side="BUY",
            units=units,
            price=price,
            cash_delta=-cost,
            realized_pnl=0.0,
            reason="signal_buy",
            position_units=new_units,
            rule_snapshot=rule_snap,
            signals=sig_snap,
        )

    def _execute_sell(
        self,
        symbol: str,
        price: float,
        ts_utc: datetime,
        reason: TradeReason,
        rule_snap: dict[str, object],
        sig_snap: dict[str, str],
    ) -> Trade | None:
        pos = self._state.positions.get(symbol)
        if pos is None or pos.units <= 0.0:
            return None
        if self._settings.sell_mode == "all":
            units = pos.units
        else:
            units = pos.units * self._settings.sell_pct
        return self._execute_sell_units(
            symbol=symbol,
            units=units,
            price=price,
            ts_utc=ts_utc,
            reason=reason,
            rule_snap=rule_snap,
            signals=sig_snap,
        )

    def _execute_sell_units(
        self,
        *,
        symbol: str,
        units: float,
        price: float,
        ts_utc: datetime,
        reason: TradeReason,
        rule_snap: dict[str, object],
        signals: dict[str, str],
    ) -> Trade | None:
        pos = self._state.positions.get(symbol)
        if pos is None or pos.units <= 0.0 or units <= 0.0 or price <= 0.0:
            return None
        units = min(units, pos.units)
        proceeds = units * price
        cost = units * pos.avg_cost
        realized = proceeds - cost
        pos.units -= units
        if pos.units < 1e-9:
            pos.units = 0.0
            pos.avg_cost = 0.0
        self._state.positions[symbol] = pos
        self._state.cash += proceeds
        self._state.today_realized_pnl += realized
        self._state.lifetime_realized_pnl += realized
        return Trade(
            trade_id=str(uuid.uuid4()),
            ts_utc=ts_utc,
            symbol=symbol,
            side="SELL",
            units=units,
            price=price,
            cash_delta=proceeds,
            realized_pnl=realized,
            reason=reason,
            position_units=pos.units,
            rule_snapshot=rule_snap,
            signals=signals,
        )

    def _rule_snapshot(self) -> dict[str, object]:
        return {
            "buy_pct": self._settings.buy_pct,
            "sell_mode": self._settings.sell_mode,
            "sell_pct": self._settings.sell_pct,
            "trigger_mode": self._settings.trigger_mode,
            "initial_deposit": self._settings.initial_deposit,
        }

    def _persist(self) -> None:
        if not self._persist_enabled:
            return
        save_trades(trades_path(), self._state, self._trades, self._daily, _TRADE_CAP)

    def _load(self) -> None:
        loaded = load_trades(trades_path(), self._settings.initial_deposit)
        if loaded is None:
            return
        self._state, self._trades, self._daily = loaded
