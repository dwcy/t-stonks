"""Trade Simulator modal screen."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Select,
    Static,
    Switch,
    TabbedContent,
    TabPane,
)

from textual.css.query import NoMatches

from goldsilver.data.models import GOLD, SILVER
from goldsilver.data.signal_stats import (
    DEFAULT_HORIZON_MINUTES,
    StrategyScore,
    score_all,
)
from goldsilver.data.signal_strategies import STRATEGY_REGISTRY
from goldsilver.data.trade_models import SellMode, SimulatorSummary, TriggerMode
from goldsilver.widgets.trade_backtest import (
    compose_backtest_pane,
    control_symbol,
    fmt_money as _fmt_money,
    fmt_pct as _fmt_pct,
    pnl_color as _pnl_color,
    refresh_day_options,
    run_and_render,
    trade_cells,
)


class TradeSimulatorScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self) -> None:
        super().__init__()
        self._rendered_trade_ids: set[str] = set()
        self._rendered_history_days: set[str] = set()
        self._bt_rendered: dict[str, set[str]] = {GOLD: set(), SILVER: set()}

    def compose(self) -> ComposeResult:
        with Container(id="trade-sim-dialog"):
            yield Label("Trade Simulator", id="trade-sim-title")
            with VerticalScroll(id="trade-sim-body"):
                with Horizontal(classes="sim-row"):
                    yield Static("", id="sim-cash", classes="sim-stat")
                    yield Static("", id="sim-today", classes="sim-stat")
                    yield Static("", id="sim-lifetime", classes="sim-stat")
                    yield Static("", id="sim-status", classes="sim-stat")
                with Horizontal(classes="sim-row"):
                    yield Static("", id="sim-analytics", classes="sim-stat")
                with Horizontal(classes="sim-row"):
                    yield Static("", id="sim-pos-gold", classes="sim-pos")
                    yield Static("", id="sim-pos-silver", classes="sim-pos")
                with Vertical(classes="sim-controls"):
                    with Horizontal(classes="sim-row sim-header-row"):
                        yield Label(
                            "Enable simulator",
                            classes="sim-header-cell sim-header-enable",
                        )
                        yield Label(
                            "Sell mode", classes="sim-header-cell sim-header-sell-mode"
                        )
                        yield Label(
                            "Sell %", classes="sim-header-cell sim-header-sell-pct"
                        )
                        yield Label(
                            "Trigger", classes="sim-header-cell sim-header-trigger"
                        )
                    with Horizontal(classes="sim-row sim-sell-row"):
                        yield Switch(value=False, id="sim-enabled")
                        with RadioSet(id="sim-sell-mode"):
                            yield RadioButton("Sell all", value=True)
                            yield RadioButton("Percent")
                        yield Input(
                            value="50", id="sim-sell-pct", classes="sim-pct-input"
                        )
                        with RadioSet(id="sim-trigger"):
                            yield RadioButton("Either", value=True)
                            yield RadioButton("Both")
                with TabbedContent(id="sim-tabs"):
                    with TabPane("Recent", id="sim-tab-recent"):
                        trades_table = DataTable(id="sim-trades", zebra_stripes=True)
                        trades_table.add_columns(
                            "Time",
                            "Symbol",
                            "Side",
                            "Units",
                            "Total units",
                            "Price",
                            "P/L",
                            "Reason",
                        )
                        yield trades_table
                    with TabPane("Trade Simulator History", id="sim-tab-history"):
                        history_table = DataTable(id="sim-history", zebra_stripes=True)
                        history_table.add_column("Date", key="date")
                        history_table.add_column("Buys", key="buys")
                        history_table.add_column("Sells", key="sells")
                        history_table.add_column("Trades", key="trades")
                        history_table.add_column("Realized P/L", key="pnl")
                        yield history_table
                    with TabPane("Signal stats", id="sim-tab-signal-stats"):
                        yield Static(
                            f"Scoring 2d of 1m bars against the close "
                            f"{DEFAULT_HORIZON_MINUTES}m after each fire…",
                            id="sim-signal-stats-note",
                        )
                        stats_table = DataTable(
                            id="sim-signal-stats", zebra_stripes=True
                        )
                        stats_table.add_columns(
                            "Strategy",
                            "Kind",
                            "Gold fires",
                            "Gold win%",
                            "Silver fires",
                            "Silver win%",
                        )
                        yield stats_table
                    yield from compose_backtest_pane(GOLD, self.app._settings)
                    yield from compose_backtest_pane(SILVER, self.app._settings)
            with Horizontal(id="trade-sim-footer"):
                yield Button("Close", id="sim-close")
                yield Button("Liquidate now", id="sim-liquidate", variant="warning")
                yield Button("Reset to $100k", id="sim-reset", variant="error")

    def on_mount(self) -> None:
        self._refresh()
        self.set_interval(1.0, self._refresh)
        refresh_day_options(self, GOLD)
        refresh_day_options(self, SILVER)
        self.run_worker(
            self._load_signal_stats(), exclusive=True, group="sim-signal-stats"
        )

    async def _load_signal_stats(self) -> None:
        service = self.app._service  # type: ignore[attr-defined]
        overrides = self.app._settings.signal_params  # type: ignore[attr-defined]
        bars_by_symbol = {}
        for symbol in (GOLD, SILVER):
            try:
                bars_by_symbol[symbol] = await service.fetch_history(
                    symbol, period="2d", interval="1m"
                )
            except Exception:
                bars_by_symbol[symbol] = []
        self._fill_signal_stats(score_all(bars_by_symbol, overrides))

    def _fill_signal_stats(self, scores: dict[str, dict[str, StrategyScore]]) -> None:
        try:
            table = self.query_one("#sim-signal-stats", DataTable)
        except NoMatches:
            return

        def _cells(score: StrategyScore | None) -> tuple[str, str]:
            if score is None or score.win_rate is None:
                return (str(score.fires) if score else "0", "—")
            return (str(score.fires), f"{score.win_rate:.0f}%")

        table.clear()
        for cls in STRATEGY_REGISTRY:
            gold_fires, gold_win = _cells(scores.get(GOLD, {}).get(cls.name))
            silver_fires, silver_win = _cells(scores.get(SILVER, {}).get(cls.name))
            table.add_row(
                cls.name, cls.kind, gold_fires, gold_win, silver_fires, silver_win
            )

    def _refresh(self) -> None:
        svc = self._service()
        last_prices = getattr(self.app, "_last_price", {})
        summary = svc.summary(last_prices)
        self._apply_summary(summary)

    def _service(self):
        return self.app._trades  # type: ignore[attr-defined]

    def _apply_summary(self, s: SimulatorSummary) -> None:
        self._set_static(
            "sim-cash",
            Text.assemble(
                ("Cash  ", "#a0a0b0"),
                (_fmt_money(s.cash), "bold #e0e0e8"),
            ),
        )
        self._set_static(
            "sim-today",
            Text.assemble(
                ("Today  ", "#a0a0b0"),
                (
                    f"{_fmt_money(s.today_realized_pnl)} ({_fmt_pct(s.today_pct)})",
                    f"bold {_pnl_color(s.today_realized_pnl)}",
                ),
            ),
        )
        self._set_static(
            "sim-lifetime",
            Text.assemble(
                ("Lifetime  ", "#a0a0b0"),
                (
                    f"{_fmt_money(s.lifetime_realized_pnl)} ({_fmt_pct(s.lifetime_pct)})",
                    f"bold {_pnl_color(s.lifetime_realized_pnl)}",
                ),
            ),
        )
        status_text = (
            "OPEN" if s.is_open else ("CLOSED" if s.liquidated_for_day else "PRE-OPEN")
        )
        status_color = "#7dff8c" if s.is_open else "#ff6b6b"
        self._set_static(
            "sim-status",
            Text.assemble(
                ("Status  ", "#a0a0b0"),
                (status_text, f"bold {status_color}"),
            ),
        )
        if s.win_rate is None:
            analytics = Text("No closed trades yet", style="dim #7a7a8a")
        else:
            analytics = Text.assemble(
                ("Win rate  ", "#a0a0b0"),
                (f"{s.win_rate:.0f}%   ", "bold #e0e0e8"),
                ("Avg win  ", "#a0a0b0"),
                (f"{_fmt_money(s.avg_win or 0.0)}   ", f"bold {_pnl_color(1.0)}"),
                ("Avg loss  ", "#a0a0b0"),
                (f"{_fmt_money(s.avg_loss or 0.0)}   ", f"bold {_pnl_color(-1.0)}"),
                ("Max drawdown  ", "#a0a0b0"),
                (f"{_fmt_money(-s.max_drawdown)}", "bold #ff9b6b"),
            )
        self._set_static("sim-analytics", analytics)
        gold_pos = next((p for p in s.positions if p.symbol == "XAU"), None)
        silver_pos = next((p for p in s.positions if p.symbol == "XAG"), None)
        self._set_static("sim-pos-gold", self._format_position("Gold", gold_pos))
        self._set_static("sim-pos-silver", self._format_position("Silver", silver_pos))
        try:
            sw = self.query_one("#sim-enabled", Switch)
            if sw.value != s.enabled:
                sw.value = s.enabled
        except Exception:
            pass
        self._populate_trades(s)
        self._populate_history(s)

    def _format_position(self, symbol: str, pos) -> Text:
        if pos is None or pos.units <= 0:
            return Text.assemble(
                (f"{symbol}  ", "#a0a0b0"),
                ("flat", "dim #7a7a8a"),
            )
        return Text.assemble(
            (f"{symbol}  ", "#a0a0b0"),
            (f"{pos.units:.4f} @ ${pos.avg_cost:,.2f}  →  ", "#e0e0e8"),
            (f"MV {_fmt_money(pos.market_value)}  ", "bold #e0e0e8"),
            (f"({_fmt_pct(pos.unrealized_pct)})", _pnl_color(pos.unrealized_pnl)),
        )

    def _set_static(self, widget_id: str, content) -> None:
        try:
            w = self.query_one(f"#{widget_id}", Static)
            w.update(content)
        except Exception:
            pass

    def _populate_trades(self, s: SimulatorSummary) -> None:
        try:
            table = self.query_one("#sim-trades", DataTable)
        except Exception:
            return
        live_ids = {t.trade_id for t in s.recent_trades}
        if not self._rendered_trade_ids.issubset(live_ids):
            table.clear()
            self._rendered_trade_ids.clear()
        for t in s.recent_trades:
            if t.trade_id in self._rendered_trade_ids:
                continue
            table.add_row(*trade_cells(t), key=t.trade_id)
            self._rendered_trade_ids.add(t.trade_id)

    def _populate_history(self, s: SimulatorSummary) -> None:
        try:
            table = self.query_one("#sim-history", DataTable)
        except Exception:
            return
        live_keys = {h.day.isoformat() for h in s.history}
        if not self._rendered_history_days.issubset(live_keys):
            table.clear()
            self._rendered_history_days.clear()
        for h in s.history:
            key = h.day.isoformat()
            pnl_cell = Text(
                _fmt_money(h.realized_pnl),
                style=f"bold {_pnl_color(h.realized_pnl)}",
            )
            if key in self._rendered_history_days:
                try:
                    table.update_cell(key, "buys", str(h.buys))
                    table.update_cell(key, "sells", str(h.sells))
                    table.update_cell(key, "trades", str(h.buys + h.sells))
                    table.update_cell(key, "pnl", pnl_cell)
                except Exception:
                    pass
                continue
            table.add_row(
                h.day.strftime("%Y-%m-%d"),
                str(h.buys),
                str(h.sells),
                str(h.buys + h.sells),
                pnl_cell,
                key=key,
            )
            self._rendered_history_days.add(key)

    async def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "sim-enabled":
            await self._service().update_settings(enabled=bool(event.value))

    async def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        rs_id = event.radio_set.id
        idx = event.index
        if rs_id == "sim-sell-mode":
            mode: SellMode = "all" if idx == 0 else "percent"
            await self._service().update_settings(sell_mode=mode)
        elif rs_id == "sim-trigger":
            mode_t: TriggerMode = "either" if idx == 0 else "both"
            await self._service().update_settings(trigger_mode=mode_t)

    async def on_select_changed(self, event: Select.Changed) -> None:
        symbol = control_symbol(event.select.id)
        if symbol is not None:
            await run_and_render(self, symbol)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        bt_symbol = control_symbol(event.input.id)
        if bt_symbol is not None:
            await run_and_render(self, bt_symbol)
            return
        if event.input.id == "sim-sell-pct":
            try:
                pct = float(event.value) / 100.0
            except ValueError:
                return
            await self._service().update_settings(sell_pct=pct)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        run_symbol = control_symbol(bid)
        if run_symbol is not None:
            await run_and_render(self, run_symbol)
        elif bid == "sim-close":
            self.dismiss()
        elif bid == "sim-liquidate":
            last_prices = getattr(self.app, "_last_price", {})
            await self._service().liquidate_now(last_prices)
            self._refresh()
        elif bid == "sim-reset":
            await self._service().reset_budget()
            self._refresh()
