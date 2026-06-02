"""Trade Simulator modal screen."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
    Static,
    Switch,
    TabbedContent,
    TabPane,
)

from goldsilver.data.trade_models import SellMode, SimulatorSummary, TriggerMode

if TYPE_CHECKING:
    from goldsilver.app import GoldSilverApp


_REASON_LABEL: dict[str, str] = {
    "signal_buy": "Buy signal",
    "signal_sell": "Sell signal",
    "eod_liquidation": "End-of-day liquidation",
    "manual_reset": "Manual reset",
}

_SYMBOL_LABEL: dict[str, str] = {
    "XAU": "Gold",
    "XAG": "Silver",
}


def _describe_reason(reason: str, side: str, signals: dict[str, str]) -> str:
    if reason == "eod_liquidation":
        return "End-of-day liquidation"
    if reason == "manual_reset":
        return "Manual reset"
    firing = [
        name.capitalize()
        for name in ("momentum", "recoil")
        if signals.get(name) == side
    ]
    if firing:
        return f"{' + '.join(firing)} {side.lower()} signal"
    return _REASON_LABEL.get(reason, reason)


def _fmt_money(v: float) -> str:
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,.2f}"


def _fmt_pct(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"


def _pnl_color(v: float) -> str:
    if v > 0.0001:
        return "#7dff8c"
    if v < -0.0001:
        return "#ff6b6b"
    return "#a0a0b0"


class TradeSimulatorScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self) -> None:
        super().__init__()
        self._rendered_trade_ids: set[str] = set()
        self._rendered_history_days: set[str] = set()

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
                    with TabPane("History", id="sim-tab-history"):
                        history_table = DataTable(id="sim-history", zebra_stripes=True)
                        history_table.add_column("Date", key="date")
                        history_table.add_column("Buys", key="buys")
                        history_table.add_column("Sells", key="sells")
                        history_table.add_column("Trades", key="trades")
                        history_table.add_column("Realized P/L", key="pnl")
                        yield history_table
            with Horizontal(id="trade-sim-footer"):
                yield Button("Close", id="sim-close")
                yield Button("Liquidate now", id="sim-liquidate", variant="warning")
                yield Button("Reset to $100k", id="sim-reset", variant="error")

    def on_mount(self) -> None:
        self._refresh()
        self.set_interval(1.0, self._refresh)

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
            local = t.ts_utc.astimezone()
            reason = _describe_reason(t.reason, t.side, t.signals)
            symbol = _SYMBOL_LABEL.get(t.symbol, t.symbol)
            pnl_str = _fmt_money(t.realized_pnl) if t.side == "SELL" else "-"
            side_color = "#7dff8c" if t.side == "BUY" else "#ff6b6b"
            side_cell = Text(t.side, style=f"bold {side_color}")
            table.add_row(
                local.strftime("%m-%d %H:%M"),
                symbol,
                side_cell,
                f"{t.units:.4f}",
                f"{t.position_units:.4f}",
                f"${t.price:,.2f}",
                pnl_str,
                reason,
                key=t.trade_id,
            )
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

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "sim-sell-pct":
            try:
                pct = float(event.value) / 100.0
            except ValueError:
                return
            await self._service().update_settings(sell_pct=pct)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "sim-close":
            self.dismiss()
        elif bid == "sim-liquidate":
            last_prices = getattr(self.app, "_last_price", {})
            await self._service().liquidate_now(last_prices)
            self._refresh()
        elif bid == "sim-reset":
            await self._service().reset_budget()
            self._refresh()
