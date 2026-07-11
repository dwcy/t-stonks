"""QuantumApp — Textual dashboard for quantum ETFs, pure-play stocks, and news."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Footer, Header, Label

from marketcore.models_macro import NewsItem, StockQuote
from marketcore.services.news_service import NewsService
from marketcore.services.stock_service import (
    StockService,
    fetch_daily_history,
    fetch_dividend_info,
    register_names,
)
from marketcore.widgets.stock_chart_screen import StockChartScreen
from marketcore.widgets.stock_tile import StockTile

from quantum.data.news_feeds import QUANTUM_NEWS_FEEDS
from quantum.data.presets import ACCENT_PRESETS, NAME_OVERRIDES
from quantum.data.settings import QuantumSettings


class QuantumApp(App[None]):
    CSS_PATH = "styles/app.tcss"
    TITLE = "quantum"
    SUB_TITLE = "quantum ETFs · pure-play stocks · news"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
    ]

    def __init__(self, *, force_wide: bool = False) -> None:
        super().__init__()
        self._force_wide = force_wide
        self._settings = QuantumSettings.load()
        register_names(NAME_OVERRIDES)

        self._tiles: dict[str, StockTile] = {}
        self._news_panel_ready = False
        self._stock_chart_screen: StockChartScreen | None = None

        tickers = [*self._settings.etf_tickers, *self._settings.stock_tickers]
        self._stock_service = StockService(
            tickers=tickers,
            handler=self._on_stock_quotes,
            stale_handler=self._on_stock_stale,
            refresh_interval_s=self._settings.refresh_interval_s,
        )
        self._news_service: NewsService | None = None
        if self._settings.news_enabled:
            self._news_service = NewsService(
                QUANTUM_NEWS_FEEDS,
                handler=self._on_news,
                stale_handler=self._on_news_stale,
            )

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="body"):
            yield Label("Quantum ETFs", classes="section-title")
            with Horizontal(id="etf-row"):
                for ticker in self._settings.etf_tickers:
                    tile = StockTile(ticker, on_chart_requested=self._show_stock_chart)
                    tile.add_class("etf-tile")
                    self._tiles[ticker] = tile
                    yield tile
            yield Label("Pure-play quantum stocks", classes="section-title")
            with Horizontal(id="stock-row"):
                for ticker in self._settings.stock_tickers:
                    tile = StockTile(ticker, on_chart_requested=self._show_stock_chart)
                    self._tiles[ticker] = tile
                    yield tile
            if self._settings.news_enabled:
                yield Label("Quantum news", classes="section-title")
                with VerticalScroll(id="news-scroll"):
                    from quantum.widgets.news_panel import QuantumNewsPanel

                    yield QuantumNewsPanel()
        yield Footer()

    async def on_mount(self) -> None:
        self._news_panel_ready = self._settings.news_enabled
        self._stock_service.start()
        if self._news_service is not None:
            self._news_service.start()

    async def on_unmount(self) -> None:
        await self._stock_service.stop()
        if self._news_service is not None:
            await self._news_service.stop()

    def _on_stock_quotes(self, quotes: list[StockQuote]) -> None:
        for quote in quotes:
            tile = self._tiles.get(quote.ticker)
            if tile is not None:
                tile.apply_quote(quote)

    def _on_stock_stale(self, since: datetime) -> None:
        for tile in self._tiles.values():
            tile.mark_stale(since)

    def _on_news(self, items: list[NewsItem]) -> None:
        panel = self._news_panel()
        if panel is not None:
            panel.apply_items(items)

    def _on_news_stale(self, since: datetime) -> None:
        panel = self._news_panel()
        if panel is not None:
            panel.mark_stale(since)

    def _news_panel(self):
        from quantum.widgets.news_panel import QuantumNewsPanel

        if not self._news_panel_ready:
            return None
        try:
            return self.query_one(QuantumNewsPanel)
        except Exception:
            return None

    async def action_refresh(self) -> None:
        await self._stock_service.refresh_now()
        if self._news_service is not None:
            await self._news_service.refresh_now()

    def _show_stock_chart(self, ticker: str) -> None:
        self.run_worker(
            self._load_stock_chart(ticker), exclusive=False, group="stock-chart"
        )

    async def _load_stock_chart(self, ticker: str) -> None:
        bars, dividend = await asyncio.gather(
            asyncio.to_thread(fetch_daily_history, ticker),
            asyncio.to_thread(fetch_dividend_info, ticker),
        )
        screen = StockChartScreen(
            ticker,
            bars,
            dividend=dividend,
            accent_color=ACCENT_PRESETS[self._settings.accent_color_name],
            on_retry=lambda: self._retry_stock_chart(ticker),
        )
        self._stock_chart_screen = screen
        self.push_screen(screen, self._on_stock_chart_closed)

    def _on_stock_chart_closed(self, _result: None) -> None:
        self._stock_chart_screen = None

    def _retry_stock_chart(self, ticker: str) -> None:
        self.run_worker(
            self._reload_stock_chart(ticker), exclusive=False, group="stock-chart"
        )

    async def _reload_stock_chart(self, ticker: str) -> None:
        bars = await asyncio.to_thread(fetch_daily_history, ticker)
        screen = self._stock_chart_screen
        if screen is not None and self.screen is screen:
            screen.apply_bars(bars)


def main() -> None:
    parser = argparse.ArgumentParser(prog="quantum")
    parser.add_argument("--force-wide", action="store_true", help="force wide layout")
    args = parser.parse_args()
    QuantumApp(force_wide=args.force_wide).run()


if __name__ == "__main__":
    main()
