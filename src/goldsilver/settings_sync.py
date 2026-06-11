"""Settings-change coordinator: diffs PlotSettings against app state and applies updates."""

from __future__ import annotations

from typing import TYPE_CHECKING

from goldsilver.data.models import GOLD, SILVER

if TYPE_CHECKING:
    from goldsilver.app import GoldSilverApp
    from goldsilver.widgets import PlotSettings


def apply_settings_change(app: GoldSilverApp, settings: PlotSettings) -> None:
    timeframe_changed = settings.timeframe_index != app._timeframe_index
    feature_changed = (
        settings.chart_kind != app._chart_kind
        or settings.show_sma != app._show_sma
        or settings.show_vwap != app._show_vwap
        or settings.show_day_refs != app._show_day_refs
    )
    dual_changed = settings.show_dual_charts != app._settings.show_dual_charts
    kind2_changed = settings.chart_kind2 != app._settings.chart_kind2
    news_changed = (
        settings.show_news_markets != app._settings.show_news_markets
        or settings.show_news_trump != app._settings.show_news_trump
    )
    congress_changed = (
        settings.show_congress_trades != app._settings.show_congress_trades
    )
    insider_changed = settings.show_insider_trades != app._settings.show_insider_trades
    stocktwits_changed = settings.show_stocktwits != app._settings.show_stocktwits
    gold_changed = settings.gold_color_name != app._settings.gold_color_name
    silver_changed = settings.silver_color_name != app._settings.silver_color_name
    columns_changed = settings.metals_columns != app._settings.metals_columns

    visible_changed = settings.visible_signals != app._settings.visible_signals
    markers_changed = (
        settings.marker_momentum_strategy != app._settings.marker_momentum_strategy
        or settings.marker_recoil_strategy != app._settings.marker_recoil_strategy
    )
    mini_tiles_changed = settings.mini_tiles != app._settings.mini_tiles
    stock_row_visible_changed = settings.show_stock_row != app._settings.show_stock_row
    stock_tickers_changed = settings.stock_tickers != app._settings.stock_tickers

    app._timeframe_index = settings.timeframe_index
    app._chart_kind = settings.chart_kind
    app._show_sma = settings.show_sma
    app._show_vwap = settings.show_vwap
    app._show_day_refs = settings.show_day_refs
    app._settings.timeframe_index = settings.timeframe_index
    app._settings.chart_kind = settings.chart_kind
    app._settings.show_dual_charts = settings.show_dual_charts
    app._settings.chart_kind2 = settings.chart_kind2
    app._settings.show_sma = settings.show_sma
    app._settings.show_vwap = settings.show_vwap
    app._settings.show_day_refs = settings.show_day_refs
    app._settings.show_news_markets = settings.show_news_markets
    app._settings.show_news_trump = settings.show_news_trump
    app._settings.show_congress_trades = settings.show_congress_trades
    app._settings.show_insider_trades = settings.show_insider_trades
    app._settings.show_stocktwits = settings.show_stocktwits
    app._settings.show_stock_row = settings.show_stock_row
    app._settings.gold_color_name = settings.gold_color_name
    app._settings.silver_color_name = settings.silver_color_name
    app._settings.metals_columns = settings.metals_columns
    app._settings.visible_signals = dict(settings.visible_signals)
    app._settings.marker_momentum_strategy = settings.marker_momentum_strategy
    app._settings.marker_recoil_strategy = settings.marker_recoil_strategy
    app._settings.mini_tiles = list(settings.mini_tiles)
    app._settings.stock_tickers = list(settings.stock_tickers)
    try:
        app._settings.save()
    except OSError:
        pass

    if news_changed:
        app._apply_news_panel()
    if congress_changed and app._congress_panel is not None:
        app._congress_panel.display = app._settings.show_congress_trades
    if insider_changed and app._insider_panel is not None:
        app._insider_panel.display = app._settings.show_insider_trades
    if stocktwits_changed and app._stocktwits_panel is not None:
        app._stocktwits_panel.display = app._settings.show_stocktwits
    if gold_changed:
        for panel in (app._panels[GOLD], app._dup_panels[GOLD]):
            panel.set_accent(app._settings.gold_rgb())
    if silver_changed:
        for panel in (app._panels[SILVER], app._dup_panels[SILVER]):
            panel.set_accent(app._settings.silver_rgb())
    if columns_changed:
        app._apply_metals_columns()
    if visible_changed:
        app._sync_visible_signals()
    if mini_tiles_changed:
        app._apply_mini_tiles()
    if stock_tickers_changed:
        app._stock_service.set_tickers(list(app._settings.stock_tickers))
        app._stock_service.start()
        if app._stock_row is not None:
            app._stock_row.apply_tickers(list(app._settings.stock_tickers))
        if app._settings.stock_tickers:
            app.run_worker(
                app._stock_service.refresh_now(),
                exclusive=False,
                group="stock-refresh",
            )
    if (
        stock_row_visible_changed or stock_tickers_changed
    ) and app._stock_row is not None:
        app._stock_row.display = bool(
            app._settings.show_stock_row and app._settings.stock_tickers
        )

    if dual_changed:
        for panel in app._dup_panels.values():
            panel.display = app._settings.show_dual_charts

    if timeframe_changed:
        app._refresh_status_bar()
        app._seed_all()
        return
    if dual_changed and app._settings.show_dual_charts:
        app._seed_all()
    elif feature_changed or kind2_changed:
        for symbol in app._panels:
            for panel, kind in app._symbol_panels_with_kind(symbol):
                panel.apply_chart_features(
                    chart_kind=kind,
                    show_sma=app._show_sma,
                    show_vwap=app._show_vwap,
                    show_day_refs=app._show_day_refs,
                )
    if markers_changed:
        app._seed_all()
