from __future__ import annotations


def test_public_surface_imports() -> None:
    from marketcore.fsutil import atomic_write_text  # noqa: F401
    from marketcore.http import make_client  # noqa: F401
    from marketcore.models import Bar, Tick  # noqa: F401
    from marketcore.models_macro import NewsItem, Signal, StockQuote  # noqa: F401
    from marketcore.paths import config_base, settings_path  # noqa: F401
    from marketcore.services.base import PollingService  # noqa: F401
    from marketcore.services.news_service import NewsService  # noqa: F401
    from marketcore.services.stock_service import StockService  # noqa: F401
    from marketcore.widgets.chart import PriceChart  # noqa: F401
    from marketcore.widgets.format import format_age  # noqa: F401
    from marketcore.widgets.stock_tile import StockTile  # noqa: F401
