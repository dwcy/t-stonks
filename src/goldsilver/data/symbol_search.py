"""Fuzzy stock-symbol lookup via the Yahoo Finance search endpoint (yfinance.Search)."""

from __future__ import annotations

import yfinance as yf
from pydantic import BaseModel, ValidationError

MAX_SEARCH_RESULTS = 8


class SymbolMatch(BaseModel):
    symbol: str
    name: str
    exchange: str = ""

    @property
    def label(self) -> str:
        suffix = f"  ({self.exchange})" if self.exchange else ""
        return f"{self.symbol} — {self.name}{suffix}"


def search_symbols(query: str, limit: int = MAX_SEARCH_RESULTS) -> list[SymbolMatch]:
    q = query.strip()
    if not q:
        return []
    try:
        result = yf.Search(q, max_results=limit, news_count=0)
        quotes = result.quotes
    except Exception:
        return []
    out: list[SymbolMatch] = []
    seen: set[str] = set()
    for raw in quotes or []:
        if not isinstance(raw, dict):
            continue
        symbol = str(raw.get("symbol") or "").strip()
        if not symbol or symbol in seen:
            continue
        name = str(raw.get("shortname") or raw.get("longname") or symbol).strip()
        exchange = str(raw.get("exchDisp") or raw.get("exchange") or "").strip()
        try:
            match = SymbolMatch(symbol=symbol, name=name, exchange=exchange)
        except ValidationError:
            continue
        seen.add(symbol)
        out.append(match)
        if len(out) >= limit:
            break
    return out
