"""Shared 'last two daily closes via yfinance' fetch, used by commodity and index polling."""

from __future__ import annotations

from datetime import datetime, timezone

import yfinance as yf


def fetch_daily_close_pair(yf_symbol: str) -> tuple[float, float, datetime] | None:
    """Returns (latest_close, previous_close, latest_bar_time_utc), or None on any failure."""
    try:
        df = yf.Ticker(yf_symbol).history(period="5d", interval="1d")
    except Exception:
        return None
    if df is None or len(df) < 2:
        return None
    closes = [float(c) for c in df["Close"].tolist() if c == c]
    if len(closes) < 2:
        return None
    last_ts = df.index[-1].to_pydatetime()
    if last_ts.tzinfo is None:
        last_ts = last_ts.replace(tzinfo=timezone.utc)
    return closes[-1], closes[-2], last_ts.astimezone(timezone.utc)
