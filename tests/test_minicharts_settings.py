"""Tests for the mini-charts settings tab, preset watchlist, and extra-row helpers."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Checkbox

from goldsilver.data.settings import AppSettings
from goldsilver.data.stock_presets import PRESET_STOCKS, extra_row_tickers
from goldsilver.widgets.minicharts_tab import MiniChartsTab, parse_tickers
from goldsilver.widgets.plot_settings import PlotSettings, PlotSettingsScreen


def _plot_settings(**overrides: object) -> PlotSettings:
    base = dict(
        timeframe_index=0,
        chart_kind="line",
        show_dual_charts=False,
        chart_kind2="candle",
        show_sma=False,
        show_vwap=False,
        show_day_refs=False,
        show_news_markets=True,
        show_news_trump=True,
        show_congress_trades=False,
        show_insider_trades=False,
        show_stocktwits=False,
        show_stock_row=True,
        show_futures=True,
        gold_color_name="Classic Gold",
        silver_color_name="Pearl",
        metals_columns=2,
    )
    base.update(overrides)
    return PlotSettings(**base)


def test_extra_row_tickers_preset_order_then_extras() -> None:
    enabled = ["BOL.ST", "ABB.ST"]
    extras = ["RUSTA.ST", "CUSTOM.ST"]

    result = extra_row_tickers(enabled, extras)

    assert result == ["ABB.ST", "BOL.ST", "RUSTA.ST", "CUSTOM.ST"]


def test_extra_row_tickers_excludes_main_row_and_dedupes() -> None:
    enabled = ["ABB.ST", "BOL.ST"]
    extras = ["ABB.ST", "LUG.ST"]

    result = extra_row_tickers(enabled, extras, exclude=["BOL.ST", "LUG.ST"])

    assert result == ["ABB.ST"]


def test_app_settings_sanitizes_new_fields() -> None:
    settings = AppSettings(
        extra_stock_tickers=[" rusta.st ", "RUSTA.ST", 5, ""],
        enabled_preset_tickers=["ABB.ST", "NOT-A-PRESET.ST", "abb.st"],
    )

    assert settings.extra_stock_tickers == ["RUSTA.ST"]
    assert settings.enabled_preset_tickers == ["ABB.ST"]


def test_app_settings_presets_default_disabled() -> None:
    settings = AppSettings()

    assert settings.enabled_preset_tickers == []
    assert settings.extra_stock_tickers == []


def test_parse_tickers_splits_and_dedupes() -> None:
    assert parse_tickers("abb.st, BOL.ST; abb.st bol.st") == ["ABB.ST", "BOL.ST"]


def test_resolve_display_name_uses_preset_without_network() -> None:
    from goldsilver.data.stock_service import _resolve_display_name

    assert _resolve_display_name("BOL.ST", None) == "Boliden"


def test_resolve_display_name_uses_override_without_network() -> None:
    from goldsilver.data.stock_service import _NAME_CACHE, _resolve_display_name

    _NAME_CACHE.pop("LUG.TO", None)
    _NAME_CACHE.pop("LUMI.ST", None)

    assert _resolve_display_name("LUG.TO", None) == "Lundin Gold"
    assert _resolve_display_name("LUMI.ST", None) == "Lundin Mining"


def test_resolve_display_name_falls_back_to_symbol() -> None:
    from goldsilver.data.stock_service import _NAME_CACHE, _resolve_display_name

    _NAME_CACHE.pop("UNKNOWN.XX", None)

    assert _resolve_display_name("UNKNOWN.XX", None) == "UNKNOWN.XX"


def test_stock_tile_header_shows_name_and_percent() -> None:
    from datetime import datetime, timezone

    from goldsilver.data.models_macro import StockQuote
    from goldsilver.widgets.stock_tile import StockTile

    tile = StockTile("VSURE.ST")
    tile.quote = StockQuote(
        ticker="VSURE.ST",
        display_name="A Very Long Company Name AB",
        price=100.0,
        previous_close=90.0,
        currency="SEK",
        time=datetime.now(timezone.utc),
    )
    plain = str(tile._render_header())

    assert "A Very Long Com…" in plain
    assert "+11.11%" in plain


class _Harness(App[None]):
    def __init__(self, state: PlotSettings) -> None:
        super().__init__()
        self._state = state
        self.emitted = 0

    def compose(self) -> ComposeResult:
        yield MiniChartsTab(self._state, emit=self._count)

    def _count(self) -> None:
        self.emitted += 1


@pytest.mark.asyncio
async def test_minicharts_tab_mounts_with_all_presets_unchecked() -> None:
    state = _plot_settings(stock_tickers=["LUG.ST"])
    app = _Harness(state)

    async with app.run_test() as pilot:
        await pilot.pause()
        checkboxes = app.query(Checkbox)

        assert len(checkboxes) == len(PRESET_STOCKS)
        assert all(not cb.value for cb in checkboxes)


@pytest.mark.asyncio
async def test_plot_settings_screen_mounts_with_two_tabs() -> None:
    from textual.widgets import TabbedContent

    state = _plot_settings(visible_signals={}, mini_tiles=["USDSEK"])
    app = App[None]()

    async with app.run_test() as pilot:
        screen = PlotSettingsScreen(
            state, on_change=lambda _s: None, on_open_math=lambda: None
        )
        await app.push_screen(screen)
        await pilot.pause()
        tabs = screen.query_one("#plot-settings-tabs", TabbedContent)

        assert tabs.tab_count == 2
        assert screen.query_one(MiniChartsTab) is not None


@pytest.mark.asyncio
async def test_minicharts_tab_preset_toggle_updates_state_and_emits() -> None:
    state = _plot_settings()
    app = _Harness(state)

    async with app.run_test() as pilot:
        checkbox = app.query_one("#preset-abb-st", Checkbox)
        checkbox.value = True
        await pilot.pause()

        assert state.enabled_preset_tickers == ["ABB.ST"]
        assert app.emitted == 1
