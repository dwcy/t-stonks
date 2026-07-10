"""Copper/oil report tickers get their reference quote from commodity_service, not yfinance."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from goldsilver.data.models_macro import CommodityQuote
from goldsilver.reports import reference_quote
from goldsilver.reports.models import ReportTicker
from goldsilver.reports.reference_quote import (
    fetch_reference_quote,
    format_reference_quote,
    quote_symbol,
)


def test_quote_symbol_uses_backtest_proxy_for_commodities() -> None:
    assert quote_symbol(ReportTicker.commodity("COPPER")) == "HG=F"
    assert quote_symbol(ReportTicker.commodity("BRENT")) == "BZ=F"


@pytest.mark.asyncio
async def test_fetch_reference_quote_uses_commodity_service_for_commodities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quote = CommodityQuote(
        symbol="COPPER",
        price=13670.0,
        previous_close=13731.0,
        time=datetime.now(timezone.utc),
    )

    async def fake_fetch(symbol: str) -> CommodityQuote:
        assert symbol == "COPPER"
        return quote

    monkeypatch.setattr(reference_quote, "fetch_commodity_quote", fake_fetch)

    result = await fetch_reference_quote(ReportTicker.commodity("COPPER"))

    assert result is quote


def test_format_reference_quote_for_commodity() -> None:
    ticker = ReportTicker.commodity("COPPER")
    quote = CommodityQuote(
        symbol="COPPER",
        price=13670.0,
        previous_close=13731.0,
        time=datetime(2026, 6, 10, 14, 30, tzinfo=timezone.utc),
    )

    text = format_reference_quote(ticker, quote)

    assert "Copper" in text
    assert "13670.00" in text
    assert "13731.00" in text
    assert "Yahoo Finance" not in text


def test_format_reference_quote_none_still_names_symbol() -> None:
    text = format_reference_quote(ReportTicker.commodity("BRENT"), None)

    assert "BRENT" in text
