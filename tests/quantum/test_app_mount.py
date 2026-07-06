from __future__ import annotations

from datetime import datetime, timezone

from marketcore.models_macro import StockQuote
from marketcore.services.news_service import NewsService
from marketcore.services.stock_service import StockService
from marketcore.widgets.stock_tile import StockTile

from quantum.app import QuantumApp
from quantum.widgets.news_panel import QuantumNewsPanel


async def test_quantum_app_mounts_and_renders(monkeypatch) -> None:
    # Keep the test offline: prevent the polling loops from hitting the network.
    monkeypatch.setattr(StockService, "start", lambda self: None)
    monkeypatch.setattr(NewsService, "start", lambda self: None)

    app = QuantumApp()
    async with app.run_test() as pilot:
        await pilot.pause()

        tiles = list(app.query(StockTile))
        expected = len(app._settings.etf_tickers) + len(app._settings.stock_tickers)
        assert len(tiles) == expected

        panel = app.query_one(QuantumNewsPanel)
        assert panel is not None

        # Feeding a quote routes to the matching tile without error.
        quote = StockQuote(
            ticker="IONQ",
            display_name="IonQ",
            price=10.0,
            previous_close=9.0,
            time=datetime.now(timezone.utc),
        )
        app._on_stock_quotes([quote])
        await pilot.pause()
        assert app._tiles["IONQ"].quote is quote
