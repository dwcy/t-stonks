"""StockService must use fast_info for price/prev close so illiquid .V/.TO names aren't stale."""

from __future__ import annotations

import pandas as pd
import pytest

from goldsilver.data import stock_service


class _FastInfo:
    def __init__(self, last: float | None, prev: float | None, currency: str) -> None:
        self.last_price = last
        self.previous_close = prev
        self.currency = currency


class _FakeTicker:
    def __init__(self, last: float | None, prev: float | None, currency: str) -> None:
        self._fi = _FastInfo(last, prev, currency)

    def history(self, period: str, interval: str) -> pd.DataFrame:
        idx = pd.to_datetime(
            ["2026-06-08 19:00:00+00:00", "2026-06-09 13:00:00+00:00"], utc=True
        )
        return pd.DataFrame({"Close": [19.46, 19.50]}, index=idx)

    @property
    def fast_info(self) -> _FastInfo:
        return self._fi


class _NoIntradayTicker(_FakeTicker):
    def history(self, period: str, interval: str) -> pd.DataFrame:
        if interval == "5m":
            return pd.DataFrame()
        idx = pd.to_datetime(
            ["2026-06-05", "2026-06-06", "2026-06-09"], utc=True
        )
        return pd.DataFrame({"Close": [22.10, 23.19, 23.70]}, index=idx)


def test_fetch_single_prefers_fast_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        stock_service.yf, "Ticker", lambda _s: _FakeTicker(21.5, 20.75, "CAD")
    )

    quote = stock_service.fetch_single_quote("LUNR.V")

    assert quote is not None
    assert quote.price == 21.5
    assert quote.previous_close == 20.75
    assert quote.currency == "CAD"
    assert quote.intraday_closes[-1] == 21.5


def test_fetch_single_falls_back_to_intraday(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        stock_service.yf, "Ticker", lambda _s: _FakeTicker(None, None, "CAD")
    )

    quote = stock_service.fetch_single_quote("LUG.TO")

    assert quote is not None
    assert quote.price == 19.50
    assert quote.previous_close == 19.46


def test_fetch_single_falls_back_to_daily_when_no_intraday(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        stock_service.yf, "Ticker", lambda _s: _NoIntradayTicker(23.70, None, "CAD")
    )

    quote = stock_service.fetch_single_quote("LUNR.V")

    assert quote is not None
    assert quote.price == 23.70
    assert quote.previous_close == 23.19
    assert quote.intraday_closes == (22.10, 23.19, 23.70)
