"""Fetch the authoritative quote for a report run and render it as prompt ground truth."""

from __future__ import annotations

import asyncio
from typing import cast

from goldsilver.data.commodity_service import fetch_commodity_quote
from goldsilver.data.models_macro import CommodityQuote, CommoditySymbol, StockQuote
from goldsilver.data.session import STOCKHOLM
from goldsilver.data.stock_service import fetch_single_quote
from goldsilver.reports.models import ReportTicker

# Metals have no Yahoo spot symbol; COMEX front-month futures track spot within ~0.5%.
_METAL_PROXY = {"XAU": "GC=F", "XAG": "SI=F"}
# Yahoo proxy used only for post-hoc verdict-accuracy backtesting (verdict_tracker.py)
# — the live reference quote below uses commodity_service.py's own fetch (Avanza for
# copper) instead, matching the Avanza app rather than COMEX's different unit/venue.
_COMMODITY_BACKTEST_PROXY = {"COPPER": "HG=F", "BRENT": "BZ=F"}


def quote_symbol(ticker: ReportTicker) -> str:
    if ticker.kind == "metal":
        return _METAL_PROXY.get(ticker.symbol, ticker.symbol)
    if ticker.kind == "commodity":
        return _COMMODITY_BACKTEST_PROXY.get(ticker.symbol, ticker.symbol)
    return ticker.symbol


async def fetch_reference_quote(
    ticker: ReportTicker,
) -> StockQuote | CommodityQuote | None:
    if ticker.kind == "commodity":
        return await fetch_commodity_quote(cast(CommoditySymbol, ticker.symbol))
    return await asyncio.to_thread(fetch_single_quote, quote_symbol(ticker))


def format_reference_quote(
    ticker: ReportTicker, quote: StockQuote | CommodityQuote | None
) -> str:
    if quote is None:
        return (
            f"No reference quote could be fetched for {ticker.symbol}. Verify the "
            f"exchange suffix and currency of this exact listing with extra care — "
            f"the same company may trade on several exchanges in different "
            f"currencies. Prefer the listing's own exchange page over aggregators."
        )
    if isinstance(quote, CommodityQuote):
        fetched = quote.time.astimezone(STOCKHOLM).strftime("%Y-%m-%d %H:%M")
        return (
            f"Last price for {ticker.label}: **{quote.price:.2f} USD** "
            f"(previous close {quote.previous_close:.2f}, "
            f"{quote.change_percent:+.2f}%). Quote timestamp {fetched} Stockholm "
            f"time, source: live market feed."
        )
    change = quote.price - quote.previous_close
    pct = (change / quote.previous_close * 100.0) if quote.previous_close else 0.0
    fetched = quote.time.astimezone(STOCKHOLM).strftime("%Y-%m-%d %H:%M")
    text = (
        f"Last price for {quote.ticker}: **{quote.price:.2f} {quote.currency}** "
        f"(previous close {quote.previous_close:.2f}, {pct:+.2f}%). "
        f"Quote timestamp {fetched} Stockholm time, source: Yahoo Finance."
    )
    if ticker.kind == "metal":
        text += (
            f" This is the COMEX front-month future ({quote_symbol(ticker)}) used "
            f"as a spot proxy for {ticker.label}."
        )
    return text
