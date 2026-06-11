from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Grid

from goldsilver.data.models_macro import StockQuote
from goldsilver.widgets.stock_tile import StockTile


TILES_PER_ROW = 4


class StockRow(Grid):
    def __init__(self, tickers: list[str]) -> None:
        super().__init__()
        self._tickers = list(tickers)
        self._tiles: dict[str, StockTile] = {}
        self.add_class("stock-row")
        self._apply_layout_classes()

    def compose(self) -> ComposeResult:
        for ticker in self._tickers:
            tile = StockTile(ticker)
            self._tiles[ticker] = tile
            yield tile

    def _apply_layout_classes(self) -> None:
        count = max(1, min(len(self._tickers), TILES_PER_ROW))
        for n in range(1, TILES_PER_ROW + 1):
            self.remove_class(f"cols-{n}")
        self.add_class(f"cols-{count}")

    def apply_quotes(self, quotes: list[StockQuote]) -> None:
        by_ticker = {q.ticker: q for q in quotes}
        for ticker, tile in self._tiles.items():
            quote = by_ticker.get(ticker)
            if quote is not None:
                tile.apply_quote(quote)

    def mark_stale(self, since: datetime) -> None:
        for tile in self._tiles.values():
            tile.mark_stale(since)

    def apply_tickers(self, tickers: list[str]) -> None:
        self._tickers = list(tickers)
        self._tiles.clear()
        self.remove_children()
        self._apply_layout_classes()
        new_tiles: list[StockTile] = []
        for ticker in self._tickers:
            tile = StockTile(ticker)
            self._tiles[ticker] = tile
            new_tiles.append(tile)
        if new_tiles:
            self.mount(*new_tiles)

    @property
    def tickers(self) -> list[str]:
        return list(self._tickers)
