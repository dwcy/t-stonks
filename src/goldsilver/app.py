from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from typing import cast

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, VerticalScroll
from textual.widgets import Footer, Header, Static

from goldsilver.data import (
    CalendarService,
    CommodityService,
    CongressTradesService,
    FxService,
    InsiderTradesService,
    MetalsService,
    NewsService,
    OmxService,
    ReturnsCalculator,
    StockService,
    StockTwitsService,
    TrumpService,
    compute_politician_stats,
)
from goldsilver.data.models import GOLD, SILVER, Bar, Tick
from goldsilver.data.models_macro import (
    CalendarSnapshot,
    CommodityQuote,
    CommoditySymbol,
    CongressTrade,
    FxPair,
    FxRate,
    InsiderTrade,
    NewsItem,
    OmxSnapshot,
    Signal,
    StockQuote,
    StockTwitMessage,
)
from goldsilver.data.settings import AppSettings
from goldsilver.data.signal_strategies import (
    SignalStrategy,
    STRATEGY_REGISTRY,
    build_strategies,
)
from goldsilver.data.history_service import HistoryService
from goldsilver.data.service import POLL_INTERVAL_S
from goldsilver.data.session import stockholm_midnight_utc, stockholm_now
from goldsilver.data.trading_hours import to_local as _to_stockholm
from goldsilver.data.trades_service import TradesService
from goldsilver.widgets import (
    CalendarPanel,
    CommodityTile,
    CongressPanel,
    DisconnectScreen,
    EditMathScreen,
    FxTile,
    InsiderPanel,
    MetalPanel,
    NewsPanel,
    OmxStrip,
    PlotSettings,
    PlotSettingsScreen,
    StockRow,
    StockTwitsPanel,
    TradeSimulatorScreen,
    build_edit_data,
)
from goldsilver.widgets.chart import ChartKind


TRUMP_SOURCE = "TRUMP"

_FX_PAIR_IDS: frozenset[str] = frozenset({"USDSEK", "CADSEK", "EURSEK"})
_COMMODITY_IDS: frozenset[str] = frozenset({"BRENT", "COPPER", "BTC"})

TIMEFRAMES: list[tuple[str, str, str, str | None]] = [
    ("today", "2d", "1m", "today"),
    ("5d", "5d", "5m", None),
    ("1mo", "1mo", "1h", None),
    ("3mo", "3mo", "1d", None),
]

STATUS_STYLES = {
    "starting": "#7a7a8a",
    "connecting": "#ffd56b",
    "connected": "#7dff8c",
    "reconnecting": "#ff9b6b",
}


class GoldSilverApp(App[None]):
    CSS_PATH = "styles/app.tcss"
    TITLE = "gold & silver"
    SUB_TITLE = (
        f"live spot via goldprice.org; H/L + ref close via Avanza "
        f"(interval: {POLL_INTERVAL_S:g}s)"
    )

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("p", "plot_settings", "Settings"),
        Binding("t", "trade_simulator", "Trade Sim"),
        Binding("r", "refresh", "Refresh"),
        Binding("z", "cycle_zoom", "Zoom"),
        Binding("h", "cycle_chart_mode", "Mode"),
        Binding("x", "toggle_crosshair", "Crosshair"),
        Binding("left", "crosshair_left", "← cursor", show=False),
        Binding("right", "crosshair_right", "cursor →", show=False),
        Binding("pageup", "crosshair_page_left", "←← cursor", show=False),
        Binding("pagedown", "crosshair_page_right", "cursor →→", show=False),
        Binding("enter", "pin_current", "Pin", show=False),
        Binding("c", "clear_pins", "Clear pins", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._settings = AppSettings.load()
        self._panels: dict[str, MetalPanel] = {}
        self._dup_panels: dict[str, MetalPanel] = {}
        self._fx_tiles: dict[FxPair, FxTile] = {}
        self._commodity_tiles: dict[CommoditySymbol, CommodityTile] = {}
        self._calendar_panel: CalendarPanel | None = None
        self._service = MetalsService(
            tick_handler=self._on_tick,
            status_handler=self._on_status,
        )
        self._history_service = HistoryService(self._service.fetch_history)
        self._calendar_service = CalendarService(handler=self._on_calendar)
        self._fx_service = FxService(
            handler=self._on_fx_rate,
            stale_handler=self._on_fx_stale,
        )
        self._commodity_service = CommodityService(
            handler=self._on_commodity,
            stale_handler=self._on_commodity_stale,
        )
        self._news_panel: NewsPanel | None = None
        self._news_service = NewsService(
            handler=self._on_news,
            stale_handler=self._on_news_stale,
        )
        self._trump_service = TrumpService(
            handler=self._on_trump,
        )
        self._omx_strip: OmxStrip | None = None
        self._omx_service = OmxService(
            handler=self._on_omx,
            stale_handler=self._on_omx_stale,
        )
        self._stock_row: StockRow | None = None
        self._stock_service = StockService(
            tickers=list(self._settings.stock_tickers),
            handler=self._on_stock_quotes,
            stale_handler=self._on_stock_stale,
        )
        self._congress_panel: CongressPanel | None = None
        self._congress_service = CongressTradesService(
            handler=self._on_congress_trades,
            stale_handler=self._on_congress_stale,
        )
        self._returns_calc = ReturnsCalculator()
        self._insider_panel: InsiderPanel | None = None
        self._insider_service = InsiderTradesService(
            handler=self._on_insider_trades,
            stale_handler=self._on_insider_stale,
        )
        self._stocktwits_panel: StockTwitsPanel | None = None
        self._stocktwits_service = StockTwitsService(
            handler=self._on_stocktwits,
            stale_handler=self._on_stocktwits_stale,
        )
        self._strategies: list[SignalStrategy] = build_strategies()
        self._strategy_by_name: dict[str, SignalStrategy] = {
            s.name: s for s in self._strategies
        }
        self._apply_param_overrides()
        self._last_price: dict[str, tuple[float, datetime]] = {}
        self._seen_news_urls: set[str] = set()
        self._seen_trump_urls: set[str] = set()
        self._connection_status = "starting"
        self._last_tick_at: datetime | None = None
        self._timeframe_index = self._settings.timeframe_index
        self._chart_kind: ChartKind = self._settings.chart_kind
        self._chart_zoom = self._settings.chart_zoom
        self._chart_mode = self._settings.chart_mode
        self._show_sma = self._settings.show_sma
        self._show_vwap = self._settings.show_vwap
        self._show_day_refs = self._settings.show_day_refs
        self._markets_news: list[NewsItem] = []
        self._trump_news: list[NewsItem] = []
        self._disconnect_screen: DisconnectScreen | None = None
        self._disconnect_dismissed = False
        self._trades = TradesService(
            self._settings.simulator,
            settings_persister=self._persist_settings,
            on_enable_changed=self._on_simulator_enabled,
        )

    @property
    def _timeframe_label(self) -> str:
        return TIMEFRAMES[self._timeframe_index][0]

    @property
    def _timeframe_period(self) -> str:
        return TIMEFRAMES[self._timeframe_index][1]

    @property
    def _timeframe_interval(self) -> str:
        return TIMEFRAMES[self._timeframe_index][2]

    @property
    def _timeframe_filter(self) -> str | None:
        return TIMEFRAMES[self._timeframe_index][3]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with VerticalScroll(id="main-scroll"):
            with Horizontal(id="macro-strip"):
                for i, tile_id in enumerate(self._settings.mini_tiles):
                    if i > 0:
                        yield Static("|", classes="mini-sep")
                    if tile_id in _FX_PAIR_IDS:
                        pair = cast(FxPair, tile_id)
                        fx_tile = FxTile(pair)
                        self._fx_tiles[pair] = fx_tile
                        yield fx_tile
                    elif tile_id in _COMMODITY_IDS:
                        symbol = cast(CommoditySymbol, tile_id)
                        cm_tile = CommodityTile(symbol)
                        self._commodity_tiles[symbol] = cm_tile
                        yield cm_tile
            omx = OmxStrip()
            self._omx_strip = omx
            yield omx
            stock_row = StockRow(list(self._settings.stock_tickers))
            self._stock_row = stock_row
            if not self._settings.show_stock_row or not self._settings.stock_tickers:
                stock_row.display = False
            yield stock_row
            with Grid(
                id="metals",
                classes=f"cards-{self._settings.metals_columns}",
            ):
                gold = MetalPanel(
                    GOLD,
                    "GOLD",
                    accent_color=self._settings.gold_rgb(),
                    classes="-gold",
                )
                silver = MetalPanel(
                    SILVER,
                    "SILVER",
                    accent_color=self._settings.silver_rgb(),
                    classes="-silver",
                )
                self._panels[GOLD] = gold
                self._panels[SILVER] = silver
                gold2 = MetalPanel(
                    GOLD,
                    "GOLD (2)",
                    accent_color=self._settings.gold_rgb(),
                    classes="-gold -dup",
                )
                silver2 = MetalPanel(
                    SILVER,
                    "SILVER (2)",
                    accent_color=self._settings.silver_rgb(),
                    classes="-silver -dup",
                )
                gold2.display = self._settings.show_dual_charts
                silver2.display = self._settings.show_dual_charts
                self._dup_panels[GOLD] = gold2
                self._dup_panels[SILVER] = silver2
                yield gold
                yield silver
                yield gold2
                yield silver2
            calendar = CalendarPanel()
            self._calendar_panel = calendar
            yield calendar
            news = NewsPanel("Markets news")
            self._news_panel = news
            yield news
            stocktwits = StockTwitsPanel()
            self._stocktwits_panel = stocktwits
            if not self._settings.show_stocktwits:
                stocktwits.display = False
            yield stocktwits
            insider = InsiderPanel()
            self._insider_panel = insider
            if not self._settings.show_insider_trades:
                insider.display = False
            yield insider
            congress = CongressPanel("Congress trades")
            self._congress_panel = congress
            if not self._settings.show_congress_trades:
                congress.display = False
            yield congress
        yield Static("", id="status-bar")
        yield Footer()

    async def on_mount(self) -> None:
        self._refresh_status_bar()
        self._sync_visible_signals()
        try:
            strip = self.query_one("#macro-strip", Horizontal)
            strip.display = bool(self._settings.mini_tiles)
        except Exception:
            pass
        self._service.start()
        self._history_service.start()
        self._calendar_service.start()
        self._fx_service.start()
        self._commodity_service.start()
        self._news_service.start()
        self._trump_service.start()
        self._omx_service.start()
        self._stock_service.start()
        self._congress_service.start()
        self._insider_service.start()
        self._stocktwits_service.start()
        self._seed_all()
        if self._settings.simulator.enabled:
            self._start_simulator_replay()

    async def on_unmount(self) -> None:
        await self._service.stop()
        await self._history_service.stop()
        await self._calendar_service.stop()
        await self._fx_service.stop()
        await self._commodity_service.stop()
        await self._news_service.stop()
        await self._trump_service.stop()
        await self._omx_service.stop()
        await self._stock_service.stop()
        await self._congress_service.stop()
        await self._insider_service.stop()
        await self._stocktwits_service.stop()

    def _seed_all(self) -> None:
        for symbol in self._panels:
            self.run_worker(
                self._seed_panel(symbol),
                exclusive=False,
                group=f"seed-{symbol}",
            )

    def _symbol_panels(self, symbol: str) -> list[MetalPanel]:
        out: list[MetalPanel] = []
        primary = self._panels.get(symbol)
        if primary is not None:
            out.append(primary)
        dup = self._dup_panels.get(symbol)
        if dup is not None and self._settings.show_dual_charts:
            out.append(dup)
        return out

    def _symbol_panels_with_kind(
        self, symbol: str
    ) -> list[tuple[MetalPanel, ChartKind]]:
        out: list[tuple[MetalPanel, ChartKind]] = []
        primary = self._panels.get(symbol)
        if primary is not None:
            out.append((primary, self._chart_kind))
        dup = self._dup_panels.get(symbol)
        if dup is not None and self._settings.show_dual_charts:
            out.append((dup, self._settings.chart_kind2))
        return out

    def _all_metal_panels(self) -> list[MetalPanel]:
        panels = list(self._panels.values())
        if self._settings.show_dual_charts:
            panels.extend(self._dup_panels.values())
        return panels

    async def _seed_panel(self, symbol: str) -> None:
        group = self._symbol_panels_with_kind(symbol)
        if not group:
            return
        if self._chart_mode == "live":
            period, interval = "2d", "1m"
        else:
            period, interval = self._timeframe_period, self._timeframe_interval
        try:
            bars = await self._service.fetch_history(
                symbol,
                period=period,
                interval=interval,
            )
        except Exception:
            return
        if self._chart_mode == "live" and bars:
            last_time = bars[-1].time.astimezone(timezone.utc)
            cutoff = last_time - timedelta(hours=24)
            bars = [b for b in bars if b.time.astimezone(timezone.utc) >= cutoff]
        elif self._timeframe_filter == "today":
            bars = _filter_to_stockholm_today(bars)
        for panel, kind in group:
            panel.seed_history(
                bars,
                chart_kind=kind,
                show_sma=self._show_sma,
                show_vwap=self._show_vwap,
                show_day_refs=self._show_day_refs,
            )
            panel.set_chart_mode(self._chart_mode)
            if self._chart_mode == "live":
                panel.set_chart_zoom(self._chart_zoom)
            panel.clear_markers()
        panels = [p for p, _ in group]
        self.run_worker(
            self._seed_stats(symbol, panels),
            exclusive=False,
            group=f"stats-{symbol}",
        )
        mom = self._strategy_by_name.get(self._settings.marker_momentum_strategy)
        rec = self._strategy_by_name.get(self._settings.marker_recoil_strategy)
        if mom is None or rec is None:
            return
        mom.reset(symbol)
        rec.reset(symbol)
        mom_history: dict[datetime, tuple[float, str]] = {}
        rec_history: dict[datetime, tuple[float, str]] = {}
        for bar in bars:
            m = mom.observe(symbol, bar.close, bar.time)
            r = rec.observe(symbol, bar.close, bar.time)
            if m.action in ("BUY", "SELL"):
                mom_history.setdefault(m.at, (bar.close, m.action))
            if r.action in ("BUY", "SELL"):
                rec_history.setdefault(r.at, (bar.close, r.action))
        for ts, (price, action) in mom_history.items():
            rec_at = rec_history.get(ts)
            heavy = rec_at is not None and rec_at[1] == action
            color = (125, 255, 140) if action == "BUY" else (255, 107, 107)
            for panel in panels:
                panel.add_marker(price, ts, color, heavy=heavy)

    async def _seed_stats(self, symbol: str, panels: list[MetalPanel]) -> None:
        try:
            bars = await self._service.fetch_history(symbol, period="1y", interval="1d")
        except Exception:
            return
        if len(bars) < 5:
            return
        week = bars[-5:]
        month = bars[-21:] if len(bars) >= 21 else bars
        year = bars
        week_high = max(b.high for b in week)
        week_low = min(b.low for b in week)
        week_avg = sum(b.close for b in week) / len(week)
        month_avg = sum(b.close for b in month) / len(month)
        year_avg = sum(b.close for b in year) / len(year)
        for panel in panels:
            panel.set_stats(
                week_high=week_high,
                week_low=week_low,
                week_avg=week_avg,
                month_avg=month_avg,
                year_avg=year_avg,
            )

    async def _on_tick(self, tick: Tick) -> None:
        self._last_tick_at = tick.time
        self._last_price[tick.symbol] = (tick.price, tick.time)
        panels = self._symbol_panels(tick.symbol)
        mom: Signal | None = None
        rec: Signal | None = None
        if panels:
            for panel in panels:
                panel.apply_tick(tick)
            signals: dict[str, Signal] = {}
            for strategy in self._strategies:
                sig = strategy.observe(tick.symbol, tick.price, tick.time)
                signals[strategy.name] = sig
                for panel in panels:
                    panel.apply_signal(sig)
            mom = signals.get(self._settings.marker_momentum_strategy)
            rec = signals.get(self._settings.marker_recoil_strategy)
            self._maybe_draw_marker(panels, tick, mom, rec)
        if self._settings.simulator.enabled:
            await self._trades.on_signal(
                symbol=tick.symbol,
                price=tick.price,
                ts_utc=tick.time,
                mom=mom,
                rec=rec,
                last_prices=self._last_price,
            )
        self._refresh_status_bar()

    def _maybe_draw_marker(
        self,
        panels: list[MetalPanel],
        tick: Tick,
        mom: Signal | None,
        rec: Signal | None,
    ) -> None:
        mom_fresh = mom is not None and mom.at == tick.time
        rec_fresh = rec is not None and rec.at == tick.time
        actions: set[str] = set()
        if mom_fresh and mom.action in ("BUY", "SELL"):
            actions.add(mom.action)
        if rec_fresh and rec.action in ("BUY", "SELL"):
            actions.add(rec.action)
        if not actions:
            return
        both_buy = (
            mom_fresh and rec_fresh and mom.action == "BUY" and rec.action == "BUY"
        )
        both_sell = (
            mom_fresh and rec_fresh and mom.action == "SELL" and rec.action == "SELL"
        )
        if "BUY" in actions:
            for panel in panels:
                panel.add_marker(tick.price, tick.time, (125, 255, 140), heavy=both_buy)
        if "SELL" in actions:
            for panel in panels:
                panel.add_marker(
                    tick.price, tick.time, (255, 107, 107), heavy=both_sell
                )

    async def _on_status(self, status: str) -> None:
        self._connection_status = status
        self._refresh_status_bar()
        if status == "reconnecting":
            self._show_disconnect_modal()
        elif status == "connected":
            self._hide_disconnect_modal()

    def _show_disconnect_modal(self) -> None:
        if self._disconnect_screen is not None or self._disconnect_dismissed:
            return
        screen = DisconnectScreen(on_user_dismiss=self._on_disconnect_dismissed)
        self._disconnect_screen = screen
        self.push_screen(screen)

    def _hide_disconnect_modal(self) -> None:
        self._disconnect_dismissed = False
        if self._disconnect_screen is not None:
            self._disconnect_screen.dismiss_programmatically()
            self._disconnect_screen = None

    def _on_disconnect_dismissed(self) -> None:
        self._disconnect_dismissed = True
        self._disconnect_screen = None

    async def _on_calendar(self, snapshot: CalendarSnapshot) -> None:
        if self._calendar_panel is not None:
            self._calendar_panel.apply_snapshot(snapshot)

    async def _on_fx_rate(self, rate: FxRate) -> None:
        tile = self._fx_tiles.get(rate.pair)
        if tile is not None:
            tile.apply_rate(rate)

    async def _on_fx_stale(self, pair: FxPair, since: datetime) -> None:
        tile = self._fx_tiles.get(pair)
        if tile is not None:
            tile.mark_stale(since)

    async def _on_commodity(self, quote: CommodityQuote) -> None:
        tile = self._commodity_tiles.get(quote.symbol)
        if tile is not None:
            tile.apply_quote(quote)

    async def _on_commodity_stale(
        self, symbol: CommoditySymbol, since: datetime
    ) -> None:
        tile = self._commodity_tiles.get(symbol)
        if tile is not None:
            tile.mark_stale(since)

    async def _on_news(self, items: list[NewsItem]) -> None:
        self._markets_news = list(items)
        self._apply_news_panel()
        first_run = not self._seen_news_urls
        new_urls = [i for i in items if i.url not in self._seen_news_urls]
        self._seen_news_urls.update(i.url for i in items)
        if first_run or not self._settings.show_news_markets:
            return
        for _ in new_urls:
            self._mark_event_on_charts(self._settings.gold_rgb())

    async def _on_news_stale(self, since: datetime) -> None:
        if self._news_panel is not None:
            self._news_panel.mark_stale(since)

    async def _on_trump(self, items: list[NewsItem]) -> None:
        self._trump_news = list(items)
        self._apply_news_panel()
        first_run = not self._seen_trump_urls
        new_urls = [i for i in items if i.url not in self._seen_trump_urls]
        self._seen_trump_urls.update(i.url for i in items)
        if first_run or not self._settings.show_news_trump:
            return
        for _ in new_urls:
            self._mark_event_on_charts((187, 154, 247))

    def _apply_metals_columns(self) -> None:
        try:
            container = self.query_one("#metals")
        except Exception:
            return
        for n in (1, 2, 3, 4):
            container.remove_class(f"cards-{n}")
        container.add_class(f"cards-{self._settings.metals_columns}")

    def _apply_mini_tiles(self) -> None:
        try:
            strip = self.query_one("#macro-strip", Horizontal)
        except Exception:
            return
        strip.remove_children()
        self._fx_tiles.clear()
        self._commodity_tiles.clear()
        new_widgets: list[FxTile | CommodityTile | Static] = []
        for i, tile_id in enumerate(self._settings.mini_tiles):
            if i > 0:
                new_widgets.append(Static("|", classes="mini-sep"))
            if tile_id in _FX_PAIR_IDS:
                pair = cast(FxPair, tile_id)
                ft = FxTile(pair)
                self._fx_tiles[pair] = ft
                new_widgets.append(ft)
            elif tile_id in _COMMODITY_IDS:
                symbol = cast(CommoditySymbol, tile_id)
                ct = CommodityTile(symbol)
                self._commodity_tiles[symbol] = ct
                new_widgets.append(ct)
        if new_widgets:
            strip.mount(*new_widgets)
        strip.display = bool(new_widgets)

    def _apply_news_panel(self) -> None:
        if self._news_panel is None:
            return
        merged: list[NewsItem] = []
        if self._settings.show_news_markets:
            merged.extend(self._markets_news)
        if self._settings.show_news_trump:
            merged.extend(self._trump_news)
        self._news_panel.replace_items(merged)

    async def _on_omx(self, snapshot: OmxSnapshot) -> None:
        if self._omx_strip is not None:
            self._omx_strip.apply_snapshot(snapshot)

    async def _on_omx_stale(self, since: datetime) -> None:
        if self._omx_strip is not None:
            self._omx_strip.mark_stale(since)

    async def _on_stock_quotes(self, quotes: list[StockQuote]) -> None:
        if self._stock_row is not None:
            self._stock_row.apply_quotes(quotes)

    async def _on_stock_stale(self, since: datetime) -> None:
        if self._stock_row is not None:
            self._stock_row.mark_stale(since)

    async def _on_congress_trades(self, trades: list[CongressTrade]) -> None:
        if self._congress_panel is None:
            return
        returns = await self._returns_calc.compute(trades)
        stats = compute_politician_stats(trades, returns, window_days=30)
        self._congress_panel.replace_data(trades, stats, returns)

    async def _on_congress_stale(self, since: datetime) -> None:
        if self._congress_panel is not None:
            self._congress_panel.mark_stale(since)

    async def _on_insider_trades(self, trades: list[InsiderTrade]) -> None:
        if self._insider_panel is not None:
            self._insider_panel.replace_trades(trades)

    async def _on_insider_stale(self, since: datetime) -> None:
        if self._insider_panel is not None:
            self._insider_panel.mark_stale(since)

    async def _on_stocktwits(self, messages: list[StockTwitMessage]) -> None:
        if self._stocktwits_panel is not None:
            self._stocktwits_panel.replace_messages(messages)

    async def _on_stocktwits_stale(self, since: datetime) -> None:
        if self._stocktwits_panel is not None:
            self._stocktwits_panel.mark_stale(since)

    def _mark_event_on_charts(self, color: tuple[int, int, int]) -> None:
        for symbol in self._panels:
            last = self._last_price.get(symbol)
            if last is None:
                continue
            price, ts = last
            for panel in self._symbol_panels(symbol):
                panel.add_marker(price, ts, color)

    def _refresh_status_bar(self) -> None:
        try:
            bar = self.query_one("#status-bar", Static)
        except Exception:
            return
        style = STATUS_STYLES.get(self._connection_status, "#7a7a8a")
        if self._last_tick_at is None:
            ago = "no ticks yet"
        else:
            local = self._last_tick_at.astimezone()
            ago = f"last tick {local.strftime('%H:%M:%S')}"
        if self._chart_mode == "live":
            mode_label = f"live {self._chart_zoom}"
        else:
            mode_label = f"history {self._timeframe_label}"
        bar.update(
            Text.assemble(
                ("● ", style),
                (f"{self._connection_status:<13}", style),
                ("  ·  ", "#3a3a4a"),
                (mode_label, "#a0a0b0"),
                ("  ·  ", "#3a3a4a"),
                (ago, "#a0a0b0"),
            )
        )

    async def action_plot_settings(self) -> None:
        current = PlotSettings(
            timeframe_index=self._timeframe_index,
            chart_kind=self._chart_kind,
            show_dual_charts=self._settings.show_dual_charts,
            chart_kind2=self._settings.chart_kind2,
            show_sma=self._show_sma,
            show_vwap=self._show_vwap,
            show_day_refs=self._show_day_refs,
            show_news_markets=self._settings.show_news_markets,
            show_news_trump=self._settings.show_news_trump,
            show_congress_trades=self._settings.show_congress_trades,
            show_insider_trades=self._settings.show_insider_trades,
            show_stocktwits=self._settings.show_stocktwits,
            show_stock_row=self._settings.show_stock_row,
            gold_color_name=self._settings.gold_color_name,
            silver_color_name=self._settings.silver_color_name,
            metals_columns=self._settings.metals_columns,
            visible_signals=dict(self._settings.visible_signals),
            marker_momentum_strategy=self._settings.marker_momentum_strategy,
            marker_recoil_strategy=self._settings.marker_recoil_strategy,
            mini_tiles=list(self._settings.mini_tiles),
            stock_tickers=list(self._settings.stock_tickers),
        )
        self.push_screen(
            PlotSettingsScreen(
                current,
                on_change=self._on_settings_change,
                on_open_math=self._open_edit_math,
            )
        )

    def _open_edit_math(self) -> None:
        data = build_edit_data(self._strategies)
        self.push_screen(
            EditMathScreen(
                data,
                on_edit=self._on_param_edit,
                on_reset=self._on_param_reset,
            )
        )

    async def action_trade_simulator(self) -> None:
        self.push_screen(TradeSimulatorScreen())

    async def _on_simulator_enabled(self) -> None:
        self._start_simulator_replay()

    def _start_simulator_replay(self) -> None:
        for symbol in (GOLD, SILVER):
            self.run_worker(
                self._replay_today_for_simulator(symbol),
                exclusive=False,
                group=f"sim-replay-{symbol}",
            )

    async def _replay_today_for_simulator(self, symbol: str) -> None:
        if not self._settings.simulator.enabled:
            return
        mom_name = self._settings.marker_momentum_strategy
        rec_name = self._settings.marker_recoil_strategy
        mom_cls = next((c for c in STRATEGY_REGISTRY if c.name == mom_name), None)
        rec_cls = next((c for c in STRATEGY_REGISTRY if c.name == rec_name), None)
        if mom_cls is None or rec_cls is None:
            return
        try:
            bars = await self._service.fetch_history(symbol, period="2d", interval="1m")
        except Exception:
            return
        if not bars:
            return
        today_local = stockholm_now().date()
        mom = mom_cls()
        rec = rec_cls()
        for bar in bars:
            m = mom.observe(symbol, bar.close, bar.time)
            r = rec.observe(symbol, bar.close, bar.time)
            if _to_stockholm(bar.time).date() != today_local:
                continue
            await self._trades.on_signal(
                symbol=symbol,
                price=bar.close,
                ts_utc=bar.time,
                mom=m,
                rec=r,
                last_prices={symbol: (bar.close, bar.time)},
            )

    def _on_param_edit(self, strategy_name: str, key: str, value: float) -> None:
        strategy = self._strategy_by_name.get(strategy_name)
        if strategy is None:
            return
        strategy.set_param(key, value)
        self._settings.signal_params.setdefault(strategy_name, {})[key] = (
            strategy.params().get(key, value)
        )
        try:
            self._settings.save()
        except OSError:
            pass

    def _on_param_reset(self, strategy_name: str) -> None:
        try:
            cls = next(c for c in STRATEGY_REGISTRY if c.name == strategy_name)
        except StopIteration:
            return
        fresh = cls()
        self._strategy_by_name[strategy_name] = fresh
        self._strategies = [
            fresh if s.name == strategy_name else s for s in self._strategies
        ]
        self._settings.signal_params.pop(strategy_name, None)
        try:
            self._settings.save()
        except OSError:
            pass

    async def action_refresh(self) -> None:
        self._connection_status = "reconnecting"
        self._refresh_status_bar()
        await self._service.stop()
        self._service.start()
        await self._calendar_service.refresh_now()
        await self._fx_service.refresh_now()
        await self._commodity_service.refresh_now()
        await self._news_service.refresh_now()
        await self._trump_service.refresh_now()
        await self._omx_service.refresh_now()
        await self._stock_service.refresh_now()
        await self._congress_service.refresh_now()
        await self._insider_service.refresh_now()
        await self._stocktwits_service.refresh_now()

    def action_cycle_zoom(self) -> None:
        if self._chart_mode != "live":
            return
        for panel in self._all_metal_panels():
            panel.cycle_chart_zoom()
        any_panel = next(iter(self._panels.values()), None)
        if any_panel is not None:
            self._chart_zoom = any_panel.chart_zoom
            self._settings.chart_zoom = self._chart_zoom
            self._persist_settings()

    def action_cycle_chart_mode(self) -> None:
        self._chart_mode = "history" if self._chart_mode == "live" else "live"
        self._settings.chart_mode = self._chart_mode
        self._persist_settings()
        self._refresh_status_bar()
        self._seed_all()

    def action_toggle_crosshair(self) -> None:
        if self._chart_mode != "live":
            return
        for panel in self._all_metal_panels():
            panel.toggle_crosshair()

    def action_crosshair_left(self) -> None:
        if self._chart_mode != "live":
            return
        for panel in self._all_metal_panels():
            panel.move_crosshair(-1)

    def action_crosshair_right(self) -> None:
        if self._chart_mode != "live":
            return
        for panel in self._all_metal_panels():
            panel.move_crosshair(1)

    def action_crosshair_page_left(self) -> None:
        if self._chart_mode != "live":
            return
        for panel in self._all_metal_panels():
            panel.move_crosshair(-60)

    def action_crosshair_page_right(self) -> None:
        if self._chart_mode != "live":
            return
        for panel in self._all_metal_panels():
            panel.move_crosshair(60)

    def action_pin_current(self) -> None:
        if self._chart_mode != "live":
            return
        for panel in self._all_metal_panels():
            panel.pin_current()

    def action_clear_pins(self) -> None:
        if self._chart_mode != "live":
            return
        for panel in self._all_metal_panels():
            panel.clear_pins()

    def _persist_settings(self) -> None:
        try:
            self._settings.save()
        except OSError:
            pass

    def _on_settings_change(self, settings: PlotSettings) -> None:
        timeframe_changed = settings.timeframe_index != self._timeframe_index
        feature_changed = (
            settings.chart_kind != self._chart_kind
            or settings.show_sma != self._show_sma
            or settings.show_vwap != self._show_vwap
            or settings.show_day_refs != self._show_day_refs
        )
        dual_changed = settings.show_dual_charts != self._settings.show_dual_charts
        kind2_changed = settings.chart_kind2 != self._settings.chart_kind2
        news_changed = (
            settings.show_news_markets != self._settings.show_news_markets
            or settings.show_news_trump != self._settings.show_news_trump
        )
        congress_changed = (
            settings.show_congress_trades != self._settings.show_congress_trades
        )
        insider_changed = (
            settings.show_insider_trades != self._settings.show_insider_trades
        )
        stocktwits_changed = settings.show_stocktwits != self._settings.show_stocktwits
        gold_changed = settings.gold_color_name != self._settings.gold_color_name
        silver_changed = settings.silver_color_name != self._settings.silver_color_name
        columns_changed = settings.metals_columns != self._settings.metals_columns

        visible_changed = settings.visible_signals != self._settings.visible_signals
        markers_changed = (
            settings.marker_momentum_strategy != self._settings.marker_momentum_strategy
            or settings.marker_recoil_strategy != self._settings.marker_recoil_strategy
        )
        mini_tiles_changed = settings.mini_tiles != self._settings.mini_tiles
        stock_row_visible_changed = (
            settings.show_stock_row != self._settings.show_stock_row
        )
        stock_tickers_changed = settings.stock_tickers != self._settings.stock_tickers

        self._timeframe_index = settings.timeframe_index
        self._chart_kind = settings.chart_kind
        self._show_sma = settings.show_sma
        self._show_vwap = settings.show_vwap
        self._show_day_refs = settings.show_day_refs
        self._settings.timeframe_index = settings.timeframe_index
        self._settings.chart_kind = settings.chart_kind
        self._settings.show_dual_charts = settings.show_dual_charts
        self._settings.chart_kind2 = settings.chart_kind2
        self._settings.show_sma = settings.show_sma
        self._settings.show_vwap = settings.show_vwap
        self._settings.show_day_refs = settings.show_day_refs
        self._settings.show_news_markets = settings.show_news_markets
        self._settings.show_news_trump = settings.show_news_trump
        self._settings.show_congress_trades = settings.show_congress_trades
        self._settings.show_insider_trades = settings.show_insider_trades
        self._settings.show_stocktwits = settings.show_stocktwits
        self._settings.show_stock_row = settings.show_stock_row
        self._settings.gold_color_name = settings.gold_color_name
        self._settings.silver_color_name = settings.silver_color_name
        self._settings.metals_columns = settings.metals_columns
        self._settings.visible_signals = dict(settings.visible_signals)
        self._settings.marker_momentum_strategy = settings.marker_momentum_strategy
        self._settings.marker_recoil_strategy = settings.marker_recoil_strategy
        self._settings.mini_tiles = list(settings.mini_tiles)
        self._settings.stock_tickers = list(settings.stock_tickers)
        try:
            self._settings.save()
        except OSError:
            pass

        if news_changed:
            self._apply_news_panel()
        if congress_changed and self._congress_panel is not None:
            self._congress_panel.display = self._settings.show_congress_trades
        if insider_changed and self._insider_panel is not None:
            self._insider_panel.display = self._settings.show_insider_trades
        if stocktwits_changed and self._stocktwits_panel is not None:
            self._stocktwits_panel.display = self._settings.show_stocktwits
        if gold_changed:
            for panel in (self._panels[GOLD], self._dup_panels[GOLD]):
                panel.set_accent(self._settings.gold_rgb())
        if silver_changed:
            for panel in (self._panels[SILVER], self._dup_panels[SILVER]):
                panel.set_accent(self._settings.silver_rgb())
        if columns_changed:
            self._apply_metals_columns()
        if visible_changed:
            self._sync_visible_signals()
        if mini_tiles_changed:
            self._apply_mini_tiles()
        if stock_tickers_changed:
            self._stock_service.set_tickers(list(self._settings.stock_tickers))
            self._stock_service.start()
            if self._stock_row is not None:
                self._stock_row.apply_tickers(list(self._settings.stock_tickers))
            if self._settings.stock_tickers:
                self.run_worker(
                    self._stock_service.refresh_now(),
                    exclusive=False,
                    group="stock-refresh",
                )
        if (
            stock_row_visible_changed or stock_tickers_changed
        ) and self._stock_row is not None:
            self._stock_row.display = bool(
                self._settings.show_stock_row and self._settings.stock_tickers
            )

        if dual_changed:
            for panel in self._dup_panels.values():
                panel.display = self._settings.show_dual_charts

        if timeframe_changed:
            self._refresh_status_bar()
            self._seed_all()
            return
        if dual_changed and self._settings.show_dual_charts:
            self._seed_all()
        elif feature_changed or kind2_changed:
            for symbol in self._panels:
                for panel, kind in self._symbol_panels_with_kind(symbol):
                    panel.apply_chart_features(
                        chart_kind=kind,
                        show_sma=self._show_sma,
                        show_vwap=self._show_vwap,
                        show_day_refs=self._show_day_refs,
                    )
        if markers_changed:
            self._seed_all()

    def _apply_param_overrides(self) -> None:
        for name, kv in self._settings.signal_params.items():
            strategy = self._strategy_by_name.get(name)
            if strategy is None:
                continue
            for key, value in kv.items():
                strategy.set_param(key, value)

    def _sync_visible_signals(self) -> None:
        names = [
            n
            for n in (s.name for s in self._strategies)
            if self._settings.visible_signals.get(n, False)
        ]
        for panel in self._all_metal_panels():
            panel.set_visible_signals(names)


def _filter_to_stockholm_today(bars: list[Bar]) -> list[Bar]:
    midnight = stockholm_midnight_utc()
    return [b for b in bars if b.time.astimezone(timezone.utc) >= midnight]


def main() -> None:
    if not sys.stdout.isatty():
        print("ok")
        return
    GoldSilverApp().run()


if __name__ == "__main__":
    main()
